"""
Opinion.trade - 'Bitcoin Up or Down' 시리즈 중 최신 topicId(marketId) 반환.
갱신 주기: 1시간.
"""
import logging
import time
from typing import Optional, Tuple, Any, Dict

from core.opinion_config import OPINION_API_KEY, OPINION_PROXY, has_proxy
from core.opinion_client import get_markets

logger = logging.getLogger(__name__)

_CACHE: Optional[tuple] = None  # (topic_id, market_dict, expires_at)
_CACHE_TTL = 3600  # 1시간

_btc_patterns = ("bitcoin up or down", "btc up or down")


def _extract_list(data: dict) -> list:
    """API 응답에서 market list 추출. errno/result 또는 code/result 형식 대응."""
    r = data.get("result") or data
    if isinstance(r, dict) and "list" in r:
        return r.get("list") or []
    if isinstance(r, list):
        return r
    return []


def _is_btc_up_down(title: str) -> bool:
    """'Bitcoin Up or Down' 또는 'BTC Up or Down' 시리즈인지."""
    t = (title or "").lower()
    return any(p in t for p in _btc_patterns)


def get_latest_bitcoin_up_down_topic_id() -> Optional[int]:
    """
    Opinion.trade 활성 시장 API를 스캔하여
    'Bitcoin Up or Down' 시리즈 중 현재(ET 기준) 가장 최신 marketId를 반환.
    갱신 주기: 1시간.

    Returns:
        int: marketId (topicId), 없으면 None
    """
    global _CACHE
    if not has_proxy() or not OPINION_API_KEY:
        logger.warning("Opinion API 키/프록시 없음")
        return None
    now = int(time.time())
    if _CACHE and len(_CACHE) >= 3 and _CACHE[2] > now:
        return _CACHE[0]
    markets = []
    page = 1
    limit = 20
    while True:
        res = get_markets(OPINION_API_KEY, OPINION_PROXY, status="activated", page=page, limit=limit)
        if not res.get("ok"):
            logger.warning("get_markets failed: %s", res.get("data"))
            break
        data = res.get("data") or {}
        lst = _extract_list(data)
        if not lst:
            break
        markets.extend(lst)
        res_inner = data.get("result")
        total = res_inner.get("total", 0) if isinstance(res_inner, dict) else 0
        if len(markets) >= total or len(lst) < limit:
            break
        page += 1
    btc_markets = [m for m in markets if _is_btc_up_down(m.get("marketTitle") or "")]
    if not btc_markets:
        logger.info("Bitcoin Up or Down 시장 없음")
        return None

    def _cutoff_ts(m):
        t = m.get("cutoffAt") or 0
        if isinstance(t, dict):
            t = 0
        try:
            t = int(float(t))
        except (TypeError, ValueError):
            t = 0
        return t // 1000 if t > 1e12 else t

    # cutoffAt: 종료 시각(Unix). 미래 시점 중 가장 가까운 것 = 현재 진행 중인 시장
    # 없으면 과거 중 cutoffAt 최대 = 가장 최근 종료된 시장
    future = [m for m in btc_markets if _cutoff_ts(m) > now]
    if future:
        chosen = min(future, key=_cutoff_ts)
    else:
        chosen = max(btc_markets, key=_cutoff_ts)
    topic_id = chosen.get("marketId")
    if topic_id is not None:
        _CACHE = (int(topic_id), chosen, now + _CACHE_TTL)
        logger.info("Bitcoin Up or Down 최신 topicId=%s (갱신: 1시간)", topic_id)
    return topic_id


def get_latest_bitcoin_up_down_market() -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """
    Bitcoin Up or Down 최신 시장 전체 데이터 반환.
    Returns:
        (topic_id, market_dict) 또는 (None, None)
    """
    global _CACHE
    tid = get_latest_bitcoin_up_down_topic_id()
    if tid is None:
        return None, None
    if _CACHE and len(_CACHE) >= 2:
        return _CACHE[0], _CACHE[1]
    return tid, None
