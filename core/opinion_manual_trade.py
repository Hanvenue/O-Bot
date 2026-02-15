"""
오봇(Opinion) 수동 거래 - 1시간 마켓(Bitcoin Up or Down) 자전거래
README 규칙: Maker(수수료 0%) + Taker 조합, MIN_PRICE_GAP / MIN_BALANCE / TIME_BEFORE_END
다중 계정 확장 가능 (Maker/Taker 계정 선택)
"""
import logging
import time
from typing import Optional, Dict, Any, List, Tuple

from config import Config
from core.opinion_config import OPINION_API_KEY, OPINION_PROXY, has_proxy
from core.opinion_btc_topic import get_latest_bitcoin_up_down_market
from core.opinion_client import get_market, get_orderbook
from core.opinion_account import opinion_account_manager, OpinionAccount

logger = logging.getLogger(__name__)

# 수동 거래 시 시간·갭 검사 생략 가능 (README 규칙은 선택 적용)
MIN_PRICE_GAP = getattr(Config, 'MIN_PRICE_GAP', 200)
MIN_BALANCE = getattr(Config, 'MIN_BALANCE', 20)
TIME_BEFORE_END = getattr(Config, 'TIME_BEFORE_END', 300)


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


def get_1h_market_for_trade(
    topic_id: Optional[int] = None,
    skip_time_check: bool = True,
    skip_gap_check: bool = True,
) -> Dict[str, Any]:
    """
    1시간 마켓(Bitcoin Up or Down) 수동 거래용 상태 반환.
    - 시장 정보, yesTokenId/noTokenId, 호가창 기반 Maker/Taker 가격
    - trade_ready, trade_direction, strategy_preview (README 규칙)
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

    # 방향: 수동 거래는 UP 기준 전략 제공 (갭 검사 스킵 시 UP 권장)
    direction = "UP"
    out["trade_ready"] = True
    out["trade_direction"] = direction
    out["trade_reason"] = "수동 거래 가능 (Maker UP + Taker DOWN)"

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
        maker_inv = maker_price_up * s
        taker_inv = taker_price_down * s
        total = maker_inv + taker_inv
        taker_fee = taker_inv * 0.002
        return {
            "status": "arbitrage_ready",
            "status_message": "자전거래 가능 - Maker(UP 수수료 0%) + Taker(DOWN)",
            "maker": {
                "side": "UP",
                "price": maker_price_up,
                "price_display": f"{int(maker_price_up*100)}¢",
                "investment": round(maker_inv, 2),
                "fee": 0,
                "account_id": maker_account.id if maker_account else None,
            },
            "taker": {
                "side": "DOWN",
                "price": taker_price_down,
                "price_display": f"{int(taker_price_down*100)}¢",
                "investment": round(taker_inv, 2),
                "fee": round(taker_fee, 4),
                "account_id": taker_account.id if taker_account else None,
            },
            "total_investment": round(total, 2),
            "guaranteed_loss": round(taker_fee, 4),
            "yes_token_id": yes_token,
            "no_token_id": no_token,
        }

    out["strategy_preview"] = _preview()
    out["yes_token_id"] = yes_token
    out["no_token_id"] = no_token
    out["maker_price_up"] = maker_price_up
    out["time_remaining"] = time_remaining
    out["success"] = True
    return out


def execute_manual_trade(
    topic_id: int,
    shares: int,
    direction: str = "UP",
    maker_account_id: Optional[int] = None,
    taker_account_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    수동 자전거래 실행.
    - Maker: direction 방향 LIMIT 주문 (수수료 0%)
    - Taker: 반대 방향으로 매칭 (수수료 발생)
    API 키/CLOB 미연동 시 안내 메시지 반환.
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

    maker_acc = opinion_account_manager.get_by_id(maker_account_id) if maker_account_id else None
    taker_acc = opinion_account_manager.get_by_id(taker_account_id) if taker_account_id else None
    if not maker_acc:
        maker_acc = accounts[0]
    if not taker_acc:
        taker_acc = next((a for a in accounts if a.id != maker_acc.id), None) or accounts[1]
    if maker_acc.id == taker_acc.id:
        return {"success": False, "error": "Maker와 Taker는 서로 다른 계정이어야 합니다."}

    direction = (direction or "UP").upper()
    if direction not in ("UP", "DOWN"):
        direction = "UP"
    shares = max(1, int(shares))
    maker_price = status.get("maker_price_up") or 0.5
    if direction == "DOWN":
        maker_price = 1.0 - maker_price
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
    CLOB를 이용한 자전거래: Maker LIMIT → Taker 매칭.
    opinion_clob_order 모듈이 있으면 호출, 없으면 스텁.
    """
    try:
        from core.opinion_clob_order import place_limit_order
    except ImportError:
        return {
            "success": False,
            "error": "Opinion CLOB 주문 모듈(opinion_clob_order)을 추가해 주세요.",
            "needs_clob": True,
        }

    token_maker = yes_token_id if direction == "UP" else no_token_id
    token_taker = no_token_id if direction == "UP" else yes_token_id
    taker_price = round(1.0 - maker_price, 2)

    # 1) Maker LIMIT 주문
    maker_res = place_limit_order(
        account=maker_account,
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
    time.sleep(2)

    # 2) Taker 주문 (반대 쪽 매칭)
    taker_res = place_limit_order(
        account=taker_account,
        token_id=token_taker,
        side="BUY",
        price=taker_price,
        size=shares,
    )
    if not taker_res.get("success"):
        # Maker 취소 시도
        try:
            from core.opinion_clob_order import cancel_order
            cancel_order(maker_account, order_id_maker)
        except Exception:
            pass
        return {
            "success": False,
            "error": f"Taker 주문 실패: {taker_res.get('error')}",
            "taker_result": taker_res,
        }

    return {
        "success": True,
        "maker_order_id": order_id_maker,
        "taker_order_id": taker_res.get("order_id") or taker_res.get("id"),
        "direction": direction,
        "maker_price": maker_price,
        "taker_price": taker_price,
        "shares": shares,
    }
