"""
Opinion CLOB SDK 주문 스텁 (실제 주문은 API 키 발급 후 연동)
- 설치: pip install opinion-clob-sdk
- .env: OPINION_API_KEY, OPINION_PROXY, 계정별 API 키(확장 시)
"""
import logging
from typing import Optional, Dict, Any

from core.opinion_account import OpinionAccount

logger = logging.getLogger(__name__)


def place_limit_order(
    account: OpinionAccount,
    token_id: str,
    side: str,
    price: float,
    size: int,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    LIMIT 주문 (Maker 또는 Taker).
    CLOB SDK 미연동 시 success=False, needs_clob=True 반환.
    """
    try:
        # 추후: from opinion_clob_sdk import ... 로 실제 주문
        # account.api_key, account.proxy 사용
        pass
    except Exception as e:
        logger.exception("place_limit_order error")
        return {"success": False, "error": str(e)}
    return {
        "success": False,
        "error": "Opinion CLOB SDK 연동 후 사용 가능합니다. API 키 발급 및 opinion-clob-sdk 설치가 필요합니다.",
        "needs_clob": True,
        "order_id": None,
    }


def cancel_order(account: OpinionAccount, order_id: str) -> Dict[str, Any]:
    """주문 취소. 미연동 시 스텁."""
    return {"success": False, "error": "CLOB 미연동", "needs_clob": True}
