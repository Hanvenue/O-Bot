"""
Opinion.trade - 'Bitcoin Up or Down' 시리즈 중 현재 진행 중인 topicId(marketId) 반환.
캐시 5분. 캐시된 마켓이 종료(cutoff 지남)되면 즉시 무효화 후 재조회.
"""
import logging
import time
from typing import Optional, Tuple, Any, Dict

from core.opinion_config import OPINION_API_KEY, OPINION_PROXY, has_proxy
from core.opinion_client import get_markets

logger = logging.getLogger(__name__)

_CACHE: Optional[tuple] = None  # (topic_id, market_dict, expires_at)
_CACHE_TTL = 300  # 5분. 종료된 마켓은 즉시 무효화(아래에서 cutoff 체크)
_last_failure_reason: Optional[str] = None  # 마지막 실패 사유 (UI 표시용)

_btc_patterns = ("bitcoin up or down", "btc up or down")


def _extract_list(data: dict) -> list:
    """API 응답에서 market list 추출. result.list / data(배열) / result 형식 대응."""
    if not data:
        return []
    # result.list (기존 형식)
    r = data.get("result") or data
    if isinstance(r, dict) and "list" in r:
        lst = r.get("list")
        if isinstance(lst, list):
            return lst
    if isinstance(r, list):
        return r
    # data가 배열인 경우 (일부 API 응답)
    d = data.get("data")
    if isinstance(d, list):
        return d
    return []


def _is_btc_up_down(title: str) -> bool:
    """'Bitcoin Up or Down' 또는 'BTC Up or Down' 시리즈인지."""
    t = (title or "").lower()
    return any(p in t for p in _btc_patterns)


def get_latest_bitcoin_up_down_topic_id(force_refresh: bool = False) -> Optional[int]:
    """
    Opinion.trade 활성 시장 API를 스캔하여
    'Bitcoin Up or Down' 시리즈 중 현재 진행 중인( cutoff > now ) marketId를 반환.
    캐시 5분; 캐시된 마켓이 종료되면 자동 재조회.
    force_refresh=True 시 캐시 무시하고 API 재조회.

    Returns:
        int: marketId (topicId), 없으면 None
    """
    global _CACHE, _last_failure_reason
    if force_refresh:
        _CACHE = None
    if not has_proxy() or not OPINION_API_KEY:
        _last_failure_reason = "API 키 또는 프록시 없음 (.env에 OPINION_API_KEY, OPINION_PROXY 또는 OPINION_PROXY_1 확인)"
        logger.warning("Opinion API 키/프록시 없음")
        return None
    now = int(time.time())
    # 캐시가 유효하고, 캐시된 마켓이 "지금 진행 중"(시작 <= now <= 종료)일 때만 재사용
    if _CACHE and len(_CACHE) >= 3 and _CACHE[2] > now:
        try:
            m = _CACHE[1]
            t = m.get("cutoffAt") or 0
            if isinstance(t, dict):
                t = 0
            else:
                t = int(float(t))
            cutoff_sec = t // 1000 if t > 1e12 else t
            start_sec = cutoff_sec - 3600
            # 진행 중인 구간이면 캐시 사용; 이미 종료됐거나 아직 시작 전이면 재조회
            if start_sec <= now <= cutoff_sec:
                return _CACHE[0]
            logger.info("캐시된 1시간 마켓이 지금 구간 아님(start=%s cutoff=%s now=%s), 재조회", start_sec, cutoff_sec, now)
        except (TypeError, ValueError, AttributeError):
            pass
        _CACHE = None
    markets = []
    page = 1
    limit = 20
    while True:
        res = get_markets(OPINION_API_KEY, OPINION_PROXY, status="activated", page=page, limit=limit)
        if not res.get("ok"):
            _last_failure_reason = "Opinion 마켓 조회 실패 (API/프록시 오류). 서버 로그: journalctl -u obot"
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
        _last_failure_reason = "활성 시장 중 'Bitcoin Up or Down' 시리즈가 없음 (Opinion 쪽에 해당 마켓이 없을 수 있음)"
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

    # 1) 지금 진행 중인 구간 우선: 시작 <= now <= 종료 (cutoff - 3600 <= now <= cutoff)
    # 2) 없으면 미래 중 가장 가까운 종료 시각
    # 3) 없으면 과거 중 가장 최근 종료
    in_progress = [m for m in btc_markets if (_cutoff_ts(m) - 3600) <= now <= _cutoff_ts(m)]
    if in_progress:
        chosen = min(in_progress, key=_cutoff_ts)
    else:
        future = [m for m in btc_markets if _cutoff_ts(m) > now]
        if future:
            chosen = min(future, key=_cutoff_ts)
        else:
            chosen = max(btc_markets, key=_cutoff_ts)
    topic_id = chosen.get("marketId")
    if topic_id is not None:
        _last_failure_reason = None
        _CACHE = (int(topic_id), chosen, now + _CACHE_TTL)
        logger.info("Bitcoin Up or Down 최신 topicId=%s (캐시 %ds, 종료 후 자동 무효)", topic_id, _CACHE_TTL)
    else:
        _last_failure_reason = "마켓 데이터에 marketId 없음"
    return topic_id


def get_last_btc_up_down_failure_reason() -> Optional[str]:
    """1시간 마켓 조회가 실패했을 때의 마지막 사유. UI/API 에러 메시지용."""
    return _last_failure_reason


def get_latest_bitcoin_up_down_market(force_refresh: bool = False) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """
    Bitcoin Up or Down 최신 시장 전체 데이터 반환.
    force_refresh=True 시 캐시 무시하고 API 재조회 (리프레시 버튼용).
    Returns:
        (topic_id, market_dict) 또는 (None, None)
    """
    global _CACHE
    tid = get_latest_bitcoin_up_down_topic_id(force_refresh=force_refresh)
    if tid is None:
        return None, None
    if _CACHE and len(_CACHE) >= 2:
        return _CACHE[0], _CACHE[1]
    return tid, None
