"""
Opinion.trade WebSocket 클라이언트 — 오더북 실시간 구독 (market_id 기준)

- 엔드포인트: wss://ws.opinion.trade?apikey={API_KEY}
- 채널: market.depth.diff (marketId로 구독)
- HEARTBEAT 30초마다 필수
- _orderbook_state: REST 스냅샷 초기화 후 depth.diff를 누적 적용한 전체 오더북 상태
  get_best_ask_from_ws() / get_full_orderbook_snapshot()으로 조회.
- _orderbook_state_ts: 오더북 상태 마지막 갱신 타임스탬프. TTL 초과 시 REST 폴백.
"""
import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

# WS 기본 URL (프록시는 REST용; WS는 공식 엔드포인트 사용)
OPINION_WS_BASE = "wss://ws.opinion.trade"
HEARTBEAT_INTERVAL = 30
RECONNECT_DELAY = 5

# WS 오더북 상태 TTL: 이 시간(초) 이상 갱신 없으면 get_best_ask_from_ws()가 None 반환 → REST 폴백
WS_ORDERBOOK_STATE_TTL = 30  # seconds

# 구독 중인 market_id 목록
_subscribed_ids: Set[int] = set()
# 연결된 상태에서 즉시 보낼 구독/해제 대기열 (live 전송용)
_pending_subscribe: Set[int] = set()
_pending_unsubscribe: Set[int] = set()
# market_id -> 마지막 수신 depth.diff(변경분) 메시지 1개만 저장. 전체 오더북 상태가 아님.
_orderbook_cache: Dict[int, Dict[str, Any]] = {}
# market_id -> 누적 오더북 상태 {"asks": {str(price): float(size)}, "bids": {...}}
_orderbook_state: Dict[int, Dict[str, Dict[str, float]]] = {}
# market_id -> 오더북 상태 마지막 갱신 시각 (time.monotonic())
_orderbook_state_ts: Dict[int, float] = {}
# market_id -> 해당 시장의 token_id 집합 (get_cached_orderbook_for_token용)
_market_token_ids: Dict[int, Set[str]] = {}
_cache_lock = threading.Lock()
_ws_stop = threading.Event()
_ws_thread: Optional[threading.Thread] = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def _parse_levels(levels_raw: Any) -> Dict[str, float]:
    """
    asks/bids 리스트를 {str(price): float(size)} dict으로 변환.
    입력 형식: [[price, size], ...] 또는 [{"price": ..., "size": ...}, ...]
    """
    result: Dict[str, float] = {}
    if not isinstance(levels_raw, list):
        return result
    for item in levels_raw:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                price, size = float(item[0]), float(item[1])
            elif isinstance(item, dict):
                price = float(item.get("price") or item.get("amount") or 0)
                size = float(item.get("size") or item.get("quantity") or 0)
            else:
                continue
            result[str(price)] = size
        except (TypeError, ValueError, KeyError):
            continue
    return result


def _extract_ob_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """WS 메시지에서 오더북 asks/bids 포함된 실제 데이터 dict 추출."""
    # data 키가 있으면 한 단계 내려감
    inner = data.get("data") or data
    if isinstance(inner, dict) and ("asks" in inner or "bids" in inner):
        return inner
    return data


def _apply_depth_diff(market_id: int, data: Dict[str, Any]) -> None:
    """
    depth.diff 메시지를 _orderbook_state에 누적 적용.
    size == 0 이면 해당 가격 레벨 제거, size > 0 이면 업데이트.
    반드시 _cache_lock 안에서 호출할 것.
    """
    ob_data = _extract_ob_data(data)
    state = _orderbook_state.setdefault(market_id, {"asks": {}, "bids": {}})
    changed = False
    for side in ("asks", "bids"):
        diff = ob_data.get(side)
        if not isinstance(diff, list):
            continue
        levels = _parse_levels(diff)
        for price_str, size in levels.items():
            if size == 0.0:
                state[side].pop(price_str, None)
            else:
                state[side][price_str] = size
            changed = True
    if changed:
        _orderbook_state_ts[market_id] = time.monotonic()


def _init_orderbook_state(market_id: int, api_key: str, proxy: str) -> None:
    """
    REST 스냅샷으로 _orderbook_state 초기화.
    WS 구독 직후 백그라운드 스레드에서 실행; 실패해도 무시 (WS diff로 자연스럽게 채워짐).
    순환 import 방지를 위해 opinion_client를 함수 내부에서 import.
    """
    try:
        from core.opinion_client import get_orderbook  # 함수 내부 import (순환 참조 방지)
    except ImportError:
        return

    with _cache_lock:
        tokens = list(_market_token_ids.get(market_id) or [])
    if not tokens:
        logger.debug("init_orderbook_state: market_id=%s token 없음, 스킵", market_id)
        return

    token_id = tokens[0]
    try:
        res = get_orderbook(token_id, api_key, proxy)
    except Exception as e:
        logger.warning("init_orderbook_state REST 조회 실패 market_id=%s: %s", market_id, e)
        return

    if not res.get("ok"):
        logger.warning("init_orderbook_state REST 응답 실패 market_id=%s", market_id)
        return

    # REST 응답에서 asks/bids 추출
    ob_raw = res.get("data") or {}
    inner = ob_raw.get("data") or ob_raw
    if not isinstance(inner, dict):
        return

    asks = _parse_levels(inner.get("asks") or [])
    bids = _parse_levels(inner.get("bids") or [])
    if not asks and not bids:
        logger.debug("init_orderbook_state: market_id=%s asks/bids 비어있음", market_id)
        return

    with _cache_lock:
        _orderbook_state[market_id] = {"asks": asks, "bids": bids}
        _orderbook_state_ts[market_id] = time.monotonic()
    logger.info("init_orderbook_state: market_id=%s 초기화 완료 (asks=%d, bids=%d)", market_id, len(asks), len(bids))


def _run_ws_loop(api_key: str):
    """백그라운드 스레드에서 asyncio 이벤트 루프 실행."""
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    try:
        _loop.run_until_complete(_opinion_ws_loop(api_key))
    except Exception as e:
        logger.exception("Opinion WS loop exited: %s", e)
    finally:
        _loop.close()


async def _opinion_ws_loop(api_key: str):
    """연결 유지, HEARTBEAT, 구독/수신 처리."""
    global _orderbook_cache
    try:
        import websockets
    except ImportError:
        logger.warning("websockets 미설치. pip install websockets 후 Opinion WS를 사용할 수 있습니다.")
        return
    url = f"{OPINION_WS_BASE}?apikey={api_key}"
    last_heartbeat = 0.0
    while not _ws_stop.is_set():
        try:
            async with websockets.connect(
                url,
                ping_interval=25,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                logger.info("Opinion WebSocket 연결됨: %s", OPINION_WS_BASE)
                # 기존 구독 복원 (재연결 시). 재연결 직후 _pending_subscribe는 clear 후 _subscribed_ids로 복원해 이중 전송 방지.
                with _cache_lock:
                    ids = list(_subscribed_ids)
                    _pending_subscribe.clear()
                for mid in ids:
                    await ws.send(
                        json.dumps(
                            {
                                "action": "SUBSCRIBE",
                                "channel": "market.depth.diff",
                                "marketId": mid,
                            }
                        )
                    )
                while not _ws_stop.is_set():
                    # live 구독/해제: 연결된 상태에서 subscribe_orderbook/unsubscribe_orderbook 호출 시 즉시 전송
                    with _cache_lock:
                        to_sub = list(_pending_subscribe)
                        _pending_subscribe.clear()
                        to_unsub = list(_pending_unsubscribe)
                        _pending_unsubscribe.clear()
                    for mid in to_sub:
                        await ws.send(
                            json.dumps(
                                {
                                    "action": "SUBSCRIBE",
                                    "channel": "market.depth.diff",
                                    "marketId": mid,
                                }
                            )
                        )
                    for mid in to_unsub:
                        # Opinion WS 스펙: action "UNSUBSCRIBE" (문서 기준)
                        await ws.send(
                            json.dumps(
                                {
                                    "action": "UNSUBSCRIBE",
                                    "channel": "market.depth.diff",
                                    "marketId": mid,
                                }
                            )
                        )
                    now = time.monotonic()
                    if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                        await ws.send(json.dumps({"action": "HEARTBEAT"}))
                        last_heartbeat = now
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=HEARTBEAT_INTERVAL * 0.5)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        data = json.loads(raw)
                        msg_type = (data.get("msgType") or data.get("type") or "").strip()
                        market_id = data.get("marketId")
                        if market_id is not None and (
                            "depth" in msg_type.lower() or "orderbook" in msg_type.lower()
                        ):
                            with _cache_lock:
                                _orderbook_cache[int(market_id)] = data
                                # depth.diff를 _orderbook_state에 누적 적용
                                _apply_depth_diff(int(market_id), data)
                        # 그 외 메시지 타입도 marketId 있으면 캐시에 넣어둠 (나중에 구조 확정 시 활용)
                        elif market_id is not None:
                            with _cache_lock:
                                _orderbook_cache.setdefault(int(market_id), data)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
        except Exception as e:
            if not _ws_stop.is_set():
                logger.warning("Opinion WS 연결 끊김, %s초 후 재연결: %s", RECONNECT_DELAY, e)
                await asyncio.sleep(RECONNECT_DELAY)
        last_heartbeat = 0.0


def start_ws(api_key: str) -> None:
    """WebSocket 스레드 시작. 이미 동작 중이면 무시."""
    global _ws_thread
    if not (api_key or "").strip():
        return
    _ws_stop.clear()
    with _cache_lock:
        if _ws_thread is not None and _ws_thread.is_alive():
            return
    _ws_thread = threading.Thread(
        target=_run_ws_loop,
        args=(api_key.strip(),),
        daemon=True,
        name="opinion-ws",
    )
    _ws_thread.start()
    logger.info("Opinion WS 스레드 시작됨.")


def stop_ws() -> None:
    """WebSocket 스레드 정지."""
    global _ws_thread
    _ws_stop.set()
    if _ws_thread is not None:
        _ws_thread.join(timeout=RECONNECT_DELAY + 5)
        _ws_thread = None
    with _cache_lock:
        _subscribed_ids.clear()
        _pending_subscribe.clear()
        _pending_unsubscribe.clear()
        _orderbook_cache.clear()
        _orderbook_state.clear()
        _orderbook_state_ts.clear()
        _market_token_ids.clear()
    logger.info("Opinion WS 스레드 정지됨.")


def subscribe_orderbook(
    market_id: int,
    token_id: Optional[str] = None,
    api_key: str = "",
    proxy: str = "",
) -> None:
    """
    오더북 변경 구독 (market.depth.diff). 재연결 시 자동 복원.
    token_id를 주면 market_id↔token_id 매핑에 저장해 get_cached_orderbook_for_token()에서 사용.
    이미 연결된 상태면 즉시 SUBSCRIBE 메시지 전송.
    api_key/proxy가 있으면 백그라운드에서 REST 스냅샷으로 오더북 초기화.
    """
    mid = int(market_id)
    with _cache_lock:
        _subscribed_ids.add(mid)
        _pending_subscribe.add(mid)
        if token_id and (tid := (token_id or "").strip()):
            _market_token_ids.setdefault(mid, set()).add(tid)

    # REST 스냅샷으로 초기 오더북 상태 구성 (백그라운드)
    if api_key and token_id:
        t = threading.Thread(
            target=_init_orderbook_state,
            args=(mid, api_key, proxy),
            daemon=True,
            name=f"opinion-ob-init-{mid}",
        )
        t.start()


def unsubscribe_orderbook(market_id: int) -> None:
    """오더북 구독 해제. 이미 연결된 상태면 즉시 UNSUBSCRIBE 전송."""
    mid = int(market_id)
    with _cache_lock:
        _subscribed_ids.discard(mid)
        _pending_unsubscribe.add(mid)
        _orderbook_cache.pop(mid, None)
        _orderbook_state.pop(mid, None)
        _orderbook_state_ts.pop(mid, None)
        _market_token_ids.pop(mid, None)


def get_cached_orderbook_for_market(market_id: int) -> Optional[Dict[str, Any]]:
    """
    market_id 기준 캐시된 depth.diff 메시지 반환.
    반환값은 전체 오더북 스냅샷이 아닌 마지막 depth.diff 메시지임.
    전체 오더북이 필요하면 get_full_orderbook_snapshot() 또는 REST get_orderbook()을 사용할 것.
    캐시가 없거나 WS 미사용 시 None.
    """
    with _cache_lock:
        return _orderbook_cache.get(int(market_id))


def get_cached_orderbook_for_token(token_id: str) -> Optional[Dict[str, Any]]:
    """
    token_id에 해당하는 시장의 캐시된 오더북 반환.
    subscribe_orderbook(market_id, token_id=...)로 매핑을 저장해 둔 경우에만 활용 가능.
    """
    tid = (token_id or "").strip()
    if not tid:
        return None
    with _cache_lock:
        for mid, tokens in _market_token_ids.items():
            if tid in tokens:
                return _orderbook_cache.get(mid)
    return None


def get_best_ask_from_ws(market_id: int) -> Optional[float]:
    """
    WS 누적 오더북 상태에서 최저 ask 가격 반환.
    상태가 없거나 asks가 비어있거나 TTL 초과(WS_ORDERBOOK_STATE_TTL 초) 시 None → REST 폴백 유도.
    """
    mid = int(market_id)
    with _cache_lock:
        state = _orderbook_state.get(mid)
        ts = _orderbook_state_ts.get(mid, 0.0)
    if not state:
        return None
    # TTL 초과: WS 업데이트가 없었으므로 REST 폴백 유도
    if time.monotonic() - ts > WS_ORDERBOOK_STATE_TTL:
        logger.debug("WS 오더북 상태 TTL 초과(market_id=%s, %.0fs), REST 폴백", mid, time.monotonic() - ts)
        return None
    asks = state.get("asks") or {}
    if not asks:
        return None
    try:
        return min(float(p) for p in asks)
    except (TypeError, ValueError):
        return None


def get_full_orderbook_snapshot(market_id: int) -> Optional[Dict[str, Any]]:
    """
    WS 누적 오더북 상태를 REST get_orderbook() 응답과 동일한 구조로 반환.
    {"asks": [{"price": p, "size": s}, ...], "bids": [...]}  (asks 오름차순, bids 내림차순)
    상태가 없으면 None.
    """
    with _cache_lock:
        state = _orderbook_state.get(int(market_id))
    if not state:
        return None
    asks_raw = state.get("asks") or {}
    bids_raw = state.get("bids") or {}
    if not asks_raw and not bids_raw:
        return None

    asks = sorted(
        [{"price": float(p), "size": s} for p, s in asks_raw.items()],
        key=lambda x: x["price"],
    )
    bids = sorted(
        [{"price": float(p), "size": s} for p, s in bids_raw.items()],
        key=lambda x: x["price"],
        reverse=True,
    )
    return {"asks": asks, "bids": bids}
