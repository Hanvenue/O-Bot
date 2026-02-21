"""
오봇(Opinion) 수동 거래 - 1시간 마켓(Bitcoin Up or Down) 자전거래
README 규칙: Maker(수수료 0%) + Taker 조합, MIN_PRICE_GAP / MIN_BALANCE / TIME_BEFORE_END
다중 계정 확장 가능 (Maker/Taker 계정 선택)
"""
import logging
import time
from typing import Optional, Dict, Any, List, Tuple

from config import Config
from core.opinion_config import OPINION_API_KEY, OPINION_PROXY, has_proxy, get_proxy_dict
from core.opinion_btc_topic import get_latest_bitcoin_up_down_market
from core.opinion_client import get_market, get_orderbook
from core.opinion_account import opinion_account_manager, OpinionAccount
from core.btc_price import btc_price_service
from core.okx_balance import get_usdt_balance_for_address

logger = logging.getLogger(__name__)

# 수동 거래 시 시간·갭 검사 생략 가능 (README 규칙은 선택 적용)
MIN_PRICE_GAP = getattr(Config, 'MIN_PRICE_GAP', 200)
MIN_BALANCE = getattr(Config, 'MIN_BALANCE', 20)
TIME_BEFORE_END = getattr(Config, 'TIME_BEFORE_END', 300)

# 실시간 자전거래: 한쪽이 올린 주문을 반대쪽이 바로 받아야 하므로 지연 최소화
POST_MAKER_DELAY_SEC = getattr(Config, 'POST_MAKER_DELAY_SEC', 0.2)  # Maker 직후 대기 (0.2초, 기존 2초 제거)
WASH_TRADE_POLL_INTERVAL_SEC = getattr(Config, 'WASH_TRADE_POLL_INTERVAL_SEC', 0.4)  # 체결 폴링 간격
WASH_TRADE_POLL_TIMEOUT_SEC = getattr(Config, 'WASH_TRADE_POLL_TIMEOUT_SEC', 10)  # 최대 대기
USE_TAKER_MARKET_ORDER = getattr(Config, 'USE_TAKER_MARKET_ORDER', True)  # Taker를 MARKET로 보내 즉시 체결 시도


def _extract_result(data: dict) -> dict:
    """API 응답에서 result 또는 result.data 추출 (시장 상세용)."""
    r = data.get("result") or data.get("data") or data
    if isinstance(r, dict) and "data" in r:
        return r.get("data") or r
    return r if isinstance(r, dict) else {}


def _orderbook_levels(ob: dict, key: str) -> list:
    """호가창에서 bids/asks 리스트 (key는 'bids' 또는 'asks'). Opinion 응답: result 또는 result.data."""
    res = ob.get("result") or ob.get("data") or ob
    if isinstance(res, dict) and "data" in res:
        res = res.get("data") or res
    levels = res.get(key) or res.get("list") or []
    return levels if isinstance(levels, list) else []


def _best_price(levels: list, want_low: bool) -> Optional[float]:
    """호가에서 최선가 추출. want_low=True면 최저가(매수 시), False면 최고가."""
    def _p(l):
        if isinstance(l, (list, tuple)) and len(l) >= 1:
            return float(l[0])
        if isinstance(l, dict):
            v = l.get("price") or l.get("amount") or l.get("size")
            return float(v) if v is not None else None
        return None
    prices = [_p(x) for x in levels if _p(x) is not None]
    if not prices:
        return None
    return min(prices) if want_low else max(prices)


def _market_start_timestamp(market: dict) -> Optional[int]:
    """시장 구간 시작 시각(Unix 초). collection.current.startTime 우선, 없으면 cutoffAt - 3600."""
    cur = market.get("collection") and market.get("collection").get("current")
    if cur and cur.get("startTime") is not None:
        try:
            t = int(float(cur["startTime"]))
            return t // 1000 if t > 1e12 else t
        except (TypeError, ValueError):
            pass
    cutoff = market.get("cutoffAt") or 0
    try:
        t = int(float(cutoff))
        if t > 1e12:
            t = t // 1000
        if t > 0:
            return t - 3600
    except (TypeError, ValueError):
        pass
    return None


def get_1h_market_for_trade(
    topic_id: Optional[int] = None,
    skip_time_check: bool = True,
    skip_gap_check: bool = True,
    shares: int = 10,
) -> Dict[str, Any]:
    """
    1시간 마켓(Bitcoin Up or Down) 수동 거래용 상태 반환.
    - 시장 정보, yesTokenId/noTokenId, 호가창 기반 Maker/Taker 가격
    - trade_ready, trade_direction, strategy_preview (shares 기준 계정 1+2 총 거래액)
    """
    out = {
        "success": False,
        "error": None,
        "topic_id": None,
        "market": None,
        "trade_ready": False,
        "trade_direction": None,
        "trade_reason": None,
        "strategy_preview": None,
    }
    if not has_proxy() or not OPINION_API_KEY:
        out["error"] = "API 키 또는 프록시를 설정해 주세요."
        return out

    tid, market_dict = get_latest_bitcoin_up_down_market()
    if topic_id is not None and tid != topic_id:
        tid = topic_id
        res = get_market(topic_id, OPINION_API_KEY, OPINION_PROXY)
        if not res.get("ok"):
            out["error"] = "시장 조회 실패"
            return out
        market_dict = _extract_result(res.get("data") or {})
        if not market_dict:
            market_dict = res.get("data") or {}
    if not tid or not market_dict:
        out["error"] = "1시간 마켓을 찾을 수 없습니다."
        return out

    out["topic_id"] = tid
    out["market"] = market_dict

    # 목록 응답에는 토큰이 없을 수 있음 → 상세 재조회
    if not (market_dict.get("yesTokenId") and market_dict.get("noTokenId")):
        res = get_market(tid, OPINION_API_KEY, OPINION_PROXY)
        if res.get("ok"):
            market_dict = _extract_result(res.get("data") or {})
            out["market"] = market_dict

    # 종료 시각 (cutoffAt: ms 또는 sec)
    cutoff = market_dict.get("cutoffAt") or 0
    try:
        cutoff = int(float(cutoff))
        if cutoff > 1e12:
            cutoff = cutoff // 1000
    except (TypeError, ValueError):
        cutoff = 0
    now = int(time.time())
    time_remaining = max(0, cutoff - now)
    if time_remaining <= 0:
        out["trade_reason"] = "시장 종료됨"
        return out

    if not skip_time_check and time_remaining > TIME_BEFORE_END:
        out["trade_reason"] = f"진입 시간 전 ({time_remaining}s 남음, {TIME_BEFORE_END}s 전부터 가능)"
        return out

    yes_token = (market_dict.get("yesTokenId") or "").strip() or None
    no_token = (market_dict.get("noTokenId") or "").strip() or None
    if not yes_token or not no_token:
        out["error"] = "시장에 yesTokenId/noTokenId가 없습니다."
        return out

    # UP = Yes 토큰 호가창 (매수 쪽 = asks 중 최저가)
    ob_yes = get_orderbook(yes_token, OPINION_API_KEY, OPINION_PROXY)
    if not ob_yes.get("ok"):
        out["error"] = "호가창 조회 실패(Yes)"
        return out
    asks_yes = _orderbook_levels(ob_yes.get("data") or {}, "asks")
    best_ask_yes = _best_price(asks_yes, want_low=True)
    if best_ask_yes is None:
        out["trade_reason"] = "Yes 호가 없음"
        return out
    maker_price_up = max(0.01, round(best_ask_yes - 0.01, 2))
    taker_price_down = round(1.0 - maker_price_up, 2)

    # 방향: GAP(시작가 vs 현재가) 기준 — 200달러 이상 상승이면 Maker=UP, 200달러 이상 하락이면 Maker=DOWN
    direction = "UP"
    gap_usd = None
    start_ts = _market_start_timestamp(market_dict)
    if start_ts is not None:
        start_price = btc_price_service.get_price_at_timestamp(start_ts)
        current_price = btc_price_service.get_current_price()
        if start_price is not None and current_price is not None:
            gap_usd = current_price - start_price
            if gap_usd >= MIN_PRICE_GAP:
                direction = "UP"   # 200달러 이상 상승 → UP을 Maker로
            elif gap_usd <= -MIN_PRICE_GAP:
                direction = "DOWN"  # 200달러 이상 하락 → DOWN을 Maker로
            else:
                # 갭이 200 미만이면 기존처럼 현재가>=시작가 여부로 결정
                direction = "UP" if current_price >= start_price else "DOWN"
    maker_price = maker_price_up if direction == "UP" else (1.0 - maker_price_up)
    taker_price = round(1.0 - maker_price, 2)
    taker_side = "DOWN" if direction == "UP" else "UP"

    out["trade_ready"] = True
    out["trade_direction"] = direction
    if gap_usd is not None:
        out["btc_gap_usd"] = round(gap_usd, 2)  # UI에서 "GAP +$200 → Maker UP" 등 표시용
    out["trade_reason"] = f"수동 거래 가능 (Maker {direction} + Taker {taker_side})"

    accounts = opinion_account_manager.get_all()
    maker_account = None
    taker_account = None
    if len(accounts) >= 2:
        maker_account = accounts[0]
        taker_account = accounts[1]
    elif len(accounts) == 1:
        maker_account = accounts[0]

    def _preview(shares: int = 10):
        s = max(1, shares)
        maker_inv = maker_price * s
        taker_inv = taker_price * s
        total = maker_inv + taker_inv
        taker_fee = taker_inv * 0.002
        return {
            "status": "arbitrage_ready",
            "status_message": f"자전거래 가능 - Maker({direction} 수수료 0%) + Taker({taker_side})",
            "maker": {
                "side": direction,
                "price": maker_price,
                "price_display": f"{int(maker_price*100)}¢",
                "investment": round(maker_inv, 2),
                "fee": 0,
                "account_id": maker_account.id if maker_account else None,
            },
            "taker": {
                "side": taker_side,
                "price": taker_price,
                "price_display": f"{int(taker_price*100)}¢",
                "investment": round(taker_inv, 2),
                "fee": round(taker_fee, 4),
                "account_id": taker_account.id if taker_account else None,
            },
            "total_investment": round(total, 2),
            "guaranteed_loss": round(taker_fee, 4),
            "yes_token_id": yes_token,
            "no_token_id": no_token,
        }

    out["strategy_preview"] = _preview(max(1, min(1000, int(shares))))
    out["yes_token_id"] = yes_token
    out["no_token_id"] = no_token
    out["maker_price_up"] = maker_price_up
    out["maker_price"] = maker_price  # 선택된 방향(direction) 기준 Maker 가격
    out["time_remaining"] = time_remaining
    out["success"] = True
    return out


def execute_manual_trade(
    topic_id: int,
    shares: int,
    direction: Optional[str] = None,
    maker_account_id: Optional[int] = None,
    taker_account_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    수동 자전거래 실행.
    - direction 미지정 시: status의 trade_direction(Maker 유리 방향) 사용.
    - maker/taker 미지정 시: 계정 목록 순서로 자동 배정 (accounts[0]=Maker, accounts[1]=Taker).
    - Maker: direction 방향 LIMIT 주문 (수수료 0%), Taker: 반대 방향 매칭.
    """
    if not has_proxy() or not OPINION_API_KEY:
        return {"success": False, "error": "API 키 또는 프록시를 설정해 주세요."}

    status = get_1h_market_for_trade(topic_id=topic_id, skip_time_check=True, skip_gap_check=True)
    if not status.get("trade_ready") or not status.get("yes_token_id"):
        return {
            "success": False,
            "error": status.get("error") or status.get("trade_reason") or "거래 조건 미충족",
        }

    accounts = opinion_account_manager.get_all()
    if len(accounts) < 2:
        return {"success": False, "error": "자전거래는 최소 2개 계정이 필요합니다."}

    # Maker/Taker 미지정 시 자동 배정 (경봇과 동일: 순서 고정 또는 추후 잔액 기준 확장 가능)
    maker_acc = opinion_account_manager.get_by_id(maker_account_id) if maker_account_id else None
    taker_acc = opinion_account_manager.get_by_id(taker_account_id) if taker_account_id else None
    if not maker_acc:
        maker_acc = accounts[0]
    if not taker_acc:
        taker_acc = next((a for a in accounts if a.id != maker_acc.id), None) or accounts[1]
    if maker_acc.id == taker_acc.id:
        return {"success": False, "error": "Maker와 Taker는 서로 다른 계정이어야 합니다."}

    # 방향 미지정 시 status의 Maker 유리 방향(trade_direction) 사용
    direction = (direction or status.get("trade_direction") or "UP").strip().upper()
    if direction not in ("UP", "DOWN"):
        direction = "UP"
    shares = max(1, int(shares))
    maker_price = status.get("maker_price") or status.get("maker_price_up") or 0.5
    if direction == "DOWN" and status.get("maker_price") is None:
        maker_price = 1.0 - (status.get("maker_price_up") or 0.5)
    taker_price = round(1.0 - maker_price, 2)

    # CLOB SDK 연동 (미설치/미연동 시 스텁)
    try:
        from core.opinion_clob_order import place_limit_order, cancel_order
    except ImportError:
        logger.warning("opinion_clob_order 미로드 → 스텁 응답")
        return {
            "success": False,
            "error": "Opinion CLOB SDK 연동 후 사용 가능합니다. API 키를 발급받아 .env에 설정하고, opinion-clob-sdk를 설치해 주세요.",
            "needs_clob": True,
            "preview": {
                "topic_id": topic_id,
                "direction": direction,
                "shares": shares,
                "maker_price": maker_price,
                "taker_price": taker_price,
                "maker_account_id": maker_acc.id,
                "taker_account_id": taker_acc.id,
            },
        }

    # 실제 주문 실행 (opinion_clob_order에서 구현)
    result = _run_wash_trade_via_clob(
        topic_id=topic_id,
        yes_token_id=status["yes_token_id"],
        no_token_id=status["no_token_id"],
        maker_account=maker_acc,
        taker_account=taker_acc,
        direction=direction,
        maker_price=maker_price,
        shares=shares,
    )
    return result


def _check_balance_for_wash_trade(
    maker_account: OpinionAccount,
    taker_account: OpinionAccount,
    maker_price: float,
    taker_price: float,
    shares: int,
) -> Tuple[bool, Optional[str]]:
    """
    자전거래 전 양쪽 계정 잔고 확인.
    Maker 필요: maker_price * shares (USDT)
    Taker 필요: taker_price * shares * 1.002 (수수료 0.2% 포함)
    부족 시 (False, "계정 N: OO USDT 부족" 형태 메시지) 반환.
    """
    maker_need = maker_price * shares
    taker_need = taker_price * shares * 1.002
    proxy_maker = get_proxy_dict(maker_account.proxy or "") if maker_account.proxy else None
    proxy_taker = get_proxy_dict(taker_account.proxy or "") if taker_account.proxy else None
    bal_maker = get_usdt_balance_for_address(maker_account.eoa, proxy_maker)
    bal_taker = get_usdt_balance_for_address(taker_account.eoa, proxy_taker)
    if bal_maker is None:
        return False, "Maker 계정 잔고를 조회할 수 없습니다."
    if bal_taker is None:
        return False, "Taker 계정 잔고를 조회할 수 없습니다."
    if bal_maker < maker_need:
        short = round(maker_need - bal_maker, 2)
        return False, f"Maker 계정(Wallet {maker_account.id}) 잔고 부족: {short} USDT 필요 (보유: {round(bal_maker, 2)} USDT)"
    if bal_taker < taker_need:
        short = round(taker_need - bal_taker, 2)
        return False, f"Taker 계정(Wallet {taker_account.id}) 잔고 부족: {short} USDT 필요 (보유: {round(bal_taker, 2)} USDT)"
    return True, None


def _run_wash_trade_via_clob(
    topic_id: int,
    yes_token_id: str,
    no_token_id: str,
    maker_account: OpinionAccount,
    taker_account: OpinionAccount,
    direction: str,
    maker_price: float,
    shares: int,
) -> Dict[str, Any]:
    """
    CLOB 실시간 자전거래: 잔고 확인 → Maker LIMIT → (최소 대기 0.2초) → Taker MARKET/LIMIT → 체결 폴링.
    - 한쪽이 올린 주문을 반대쪽이 바로 받지 못하면 실패하므로, Maker 직후 2초 대기를 제거하고
      POST_MAKER_DELAY_SEC(0.2초)만 둔 뒤 Taker를 즉시 전송. Taker는 기본 MARKET로 즉시 체결 시도.
    - 미체결 시 양쪽 취소 후 에러 반환.
    """
    try:
        from core.opinion_clob_order import (
            place_limit_order,
            place_market_order,
            cancel_order,
            get_order_status,
        )
    except ImportError:
        return {
            "success": False,
            "error": "Opinion CLOB 주문 모듈(opinion_clob_order)을 추가해 주세요.",
            "needs_clob": True,
        }

    token_maker = yes_token_id if direction == "UP" else no_token_id
    token_taker = no_token_id if direction == "UP" else yes_token_id
    taker_price = round(1.0 - maker_price, 2)

    # 0) 잔고 사전 검증
    ok, err = _check_balance_for_wash_trade(maker_account, taker_account, maker_price, taker_price, shares)
    if not ok:
        return {"success": False, "error": err}

    # 1) Maker LIMIT 주문 (호가창에 걸어 둠)
    maker_res = place_limit_order(
        account=maker_account,
        market_id=topic_id,
        token_id=token_maker,
        side="BUY",
        price=maker_price,
        size=shares,
    )
    if not maker_res.get("success"):
        return {
            "success": False,
            "error": f"Maker 주문 실패: {maker_res.get('error')}",
            "maker_result": maker_res,
        }

    order_id_maker = maker_res.get("order_id") or maker_res.get("id")
    if not order_id_maker:
        return {"success": False, "error": "Maker 주문 ID를 받지 못했습니다.", "maker_result": maker_res}

    # 실시간: Maker 직후 최소 대기만 하고 바로 Taker 전송 (기존 2초 제거 → 0.2초)
    time.sleep(POST_MAKER_DELAY_SEC)

    # 2) Taker 주문 — MARKET로 즉시 체결 시도 (반대쪽이 '바로 받지 못하면 실패' 방지)
    place_taker = place_market_order if USE_TAKER_MARKET_ORDER else place_limit_order
    taker_res = place_taker(
        account=taker_account,
        market_id=topic_id,
        token_id=token_taker,
        side="BUY",
        price=taker_price,
        size=shares,
    )
    if not taker_res.get("success"):
        try:
            cancel_order(maker_account, order_id_maker)
        except Exception:
            pass
        return {
            "success": False,
            "error": f"Taker 주문 실패: {taker_res.get('error')}",
            "taker_result": taker_res,
        }

    order_id_taker = taker_res.get("order_id") or taker_res.get("id")
    if not order_id_taker:
        try:
            cancel_order(maker_account, order_id_maker)
        except Exception:
            pass
        return {"success": False, "error": "Taker 주문 ID를 받지 못했습니다.", "taker_result": taker_res}

    # 3) 체결 확인 (폴링 간격 단축으로 실시간에 가깝게 감지)
    deadline = time.time() + WASH_TRADE_POLL_TIMEOUT_SEC
    interval = WASH_TRADE_POLL_INTERVAL_SEC
    maker_filled = False
    taker_filled = False
    while time.time() < deadline:
        sm = get_order_status(maker_account, order_id_maker)
        st = get_order_status(taker_account, order_id_taker)
        maker_filled = sm.get("filled", False)
        taker_filled = st.get("filled", False)
        if maker_filled and taker_filled:
            return {
                "success": True,
                "maker_order_id": order_id_maker,
                "taker_order_id": order_id_taker,
                "direction": direction,
                "maker_price": maker_price,
                "taker_price": taker_price,
                "shares": shares,
            }
        time.sleep(interval)

    # 4) 미체결 시 양쪽 취소
    try:
        cancel_order(maker_account, order_id_maker)
    except Exception:
        pass
    try:
        cancel_order(taker_account, order_id_taker)
    except Exception:
        pass
    return {
        "success": False,
        "error": f"미체결: {int(WASH_TRADE_POLL_TIMEOUT_SEC)}초 내 양쪽 체결되지 않아 주문을 취소했습니다.",
        "maker_order_id": order_id_maker,
        "taker_order_id": order_id_taker,
    }
