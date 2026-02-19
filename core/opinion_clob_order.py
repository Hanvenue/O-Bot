"""
Opinion CLOB SDK 주문 연동
- place_limit_order: LIMIT BUY 주문 (account.api_key + account.proxy, 계정별 CLOB PK/Multisig)
- cancel_order: 주문 취소
- get_order_status: 주문 체결 상태 조회
- 에러 시 opinion_errors.interpret_opinion_api_response() 경유
"""
import logging
import os
from typing import Optional, Dict, Any

from core.opinion_account import OpinionAccount
from core.opinion_config import get_proxy_dict
from core.opinion_errors import interpret_opinion_api_response

logger = logging.getLogger(__name__)

# CLOB SDK용 호스트 (OpenAPI 베이스; /openapi 제외)
OPINION_CLOB_HOST = os.getenv("OPINION_CLOB_HOST", "https://proxy.opinion.trade:8443")
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")


def _get_clob_credentials(account: OpinionAccount) -> Optional[tuple]:
    """
    계정별 CLOB 전용 private_key, multi_sig_addr 반환.
    .env: OPINION_CLOB_PK_1, OPINION_MULTISIG_1 / _2 등 (account.id 기준).
    """
    aid = getattr(account, "id", 1)
    pk = (os.getenv(f"OPINION_CLOB_PK_{aid}") or "").strip()
    multi_sig = (os.getenv(f"OPINION_MULTISIG_{aid}") or "").strip()
    if not pk or not multi_sig:
        return None
    if not multi_sig.startswith("0x"):
        multi_sig = "0x" + multi_sig
    return (pk, multi_sig)


def _get_clob_client(account: OpinionAccount):
    """
    Opinion CLOB SDK Client 생성.
    account.api_key, account.proxy 사용. 프록시는 HTTP_PROXY/HTTPS_PROXY로 설정 후 복원.
    """
    creds = _get_clob_credentials(account)
    if not creds:
        return None
    private_key, multi_sig_addr = creds
    try:
        from opinion_clob_sdk import Client
        from opinion_clob_sdk.chain.py_order_utils.model.order import PlaceOrderDataInput
        from opinion_clob_sdk.chain.py_order_utils.model.sides import OrderSide
        from opinion_clob_sdk.chain.py_order_utils.model.order_type import LIMIT_ORDER
    except ImportError as e:
        logger.warning("opinion_clob_sdk import failed: %s", e)
        return None

    # 프록시가 있으면 요청 시점에만 환경변수로 설정 (SDK 내부 requests가 사용)
    proxy_str = (account.proxy or "").strip()
    old_http = os.environ.pop("HTTP_PROXY", None)
    old_https = os.environ.pop("HTTPS_PROXY", None)
    if proxy_str and ":" in proxy_str:
        parts = proxy_str.split(":")
        if len(parts) == 4:
            ip, port, user, password = parts
            proxy_url = f"http://{user}:{password}@{ip}:{port}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
    try:
        client = Client(
            host=OPINION_CLOB_HOST,
            apikey=account.api_key,
            chain_id=56,
            rpc_url=BSC_RPC_URL,
            private_key=private_key,
            multi_sig_addr=multi_sig_addr,
        )
        return client
    finally:
        if old_http is not None:
            os.environ["HTTP_PROXY"] = old_http
        if old_https is not None:
            os.environ["HTTPS_PROXY"] = old_https
        elif proxy_str:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)


def place_limit_order(
    account: OpinionAccount,
    market_id: int,
    token_id: str,
    side: str,
    price: float,
    size: int,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    LIMIT 주문 (Maker 또는 Taker).
    - market_id: Opinion marketId (topic_id).
    - side: "BUY" (SELL은 필요 시 확장).
    - price: 0.01~0.99.
    - size: 주문 수량(샤드). makerAmountInQuoteToken = price * size (USDT).
    """
    try:
        from opinion_clob_sdk.chain.py_order_utils.model.order import PlaceOrderDataInput
        from opinion_clob_sdk.chain.py_order_utils.model.sides import OrderSide
        from opinion_clob_sdk.chain.py_order_utils.model.order_type import LIMIT_ORDER
    except ImportError:
        return {
            "success": False,
            "error": "Opinion CLOB SDK 연동 후 사용 가능합니다. pip install opinion-clob-sdk 및 .env에 CLOB 키 설정이 필요합니다.",
            "needs_clob": True,
            "order_id": None,
        }

    client = _get_clob_client(account)
    if client is None:
        return {
            "success": False,
            "error": "CLOB 주문을 위해 해당 계정의 OPINION_CLOB_PK_{id}, OPINION_MULTISIG_{id}를 .env에 설정해 주세요.",
            "needs_clob": True,
            "order_id": None,
        }

    side_val = OrderSide.BUY if (side or "BUY").strip().upper() == "BUY" else OrderSide.SELL
    amount_quote = max(0.01, float(price) * max(1, int(size)))

    try:
        data = PlaceOrderDataInput(
            marketId=int(market_id),
            tokenId=(token_id or "").strip(),
            side=side_val,
            orderType=LIMIT_ORDER,
            price=str(round(float(price), 2)),
            makerAmountInQuoteToken=str(round(amount_quote, 2)),
        )
        result = client.place_order(data, check_approval=False)
        order_id = None
        if hasattr(result, "result") and hasattr(result.result, "data"):
            data_obj = result.result.data
            if hasattr(data_obj, "order_id"):
                order_id = getattr(data_obj, "order_id", None)
            if order_id is None and hasattr(data_obj, "id"):
                order_id = getattr(data_obj, "id", None)
        if order_id is None and hasattr(result, "result"):
            r = result.result
            if hasattr(r, "order_id"):
                order_id = r.order_id
            elif isinstance(getattr(r, "data", None), dict):
                order_id = (r.data or {}).get("order_id") or (r.data or {}).get("id")
        if order_id is None and isinstance(result, dict):
            order_id = result.get("order_id") or result.get("id")
        return {"success": True, "order_id": str(order_id) if order_id else None, "id": order_id}
    except Exception as e:
        err_msg = str(e)
        logger.exception("place_limit_order error: %s", err_msg)
        if hasattr(e, "status") and hasattr(e, "body"):
            interpreted = interpret_opinion_api_response(
                getattr(e, "status", 500),
                getattr(e, "body", None) if isinstance(getattr(e, "body", None), dict) else None,
                context="CLOB 주문",
            )
            err_msg = interpreted.get("user_message") or err_msg
        return {"success": False, "error": err_msg, "order_id": None}


def cancel_order(account: OpinionAccount, order_id: str) -> Dict[str, Any]:
    """주문 취소."""
    if not order_id or not isinstance(order_id, str):
        return {"success": False, "error": "order_id가 필요합니다.", "needs_clob": False}
    try:
        from opinion_clob_sdk import Client
    except ImportError:
        return {"success": False, "error": "opinion-clob-sdk 미설치", "needs_clob": True}

    client = _get_clob_client(account)
    if client is None:
        return {"success": False, "error": "CLOB 계정 설정 없음 (OPINION_CLOB_PK_*, OPINION_MULTISIG_*)", "needs_clob": True}

    try:
        client.cancel_order(order_id)
        return {"success": True}
    except Exception as e:
        err_msg = str(e)
        logger.warning("cancel_order error: %s", err_msg)
        if hasattr(e, "status") and hasattr(e, "body"):
            interpreted = interpret_opinion_api_response(
                getattr(e, "status", 500),
                getattr(e, "body", None) if isinstance(getattr(e, "body", None), dict) else None,
                context="CLOB 취소",
            )
            err_msg = interpreted.get("user_message") or err_msg
        return {"success": False, "error": err_msg}


def get_order_status(account: OpinionAccount, order_id: str) -> Dict[str, Any]:
    """
    주문 체결 상태 조회.
    Returns:
        success, filled (bool), status (str), raw (응답 참고용)
    """
    if not order_id or not isinstance(order_id, str):
        return {"success": False, "filled": False, "status": "invalid", "error": "order_id 필요"}
    try:
        from opinion_clob_sdk import Client
    except ImportError:
        return {"success": False, "filled": False, "status": "unknown", "error": "opinion-clob-sdk 미설치"}

    client = _get_clob_client(account)
    if client is None:
        return {"success": False, "filled": False, "status": "unknown", "error": "CLOB 계정 설정 없음"}

    try:
        result = client.get_order_by_id(order_id)
        filled = False
        status_str = "unknown"
        if hasattr(result, "result") and hasattr(result.result, "data"):
            data = result.result.data
            if hasattr(data, "status"):
                status_str = str(getattr(data, "status", ""))
            if hasattr(data, "filled"):
                filled = bool(getattr(data, "filled", False))
            if hasattr(data, "order_status"):
                status_str = str(getattr(data, "order_status", status_str))
        if isinstance(getattr(result, "result", None), dict):
            data = (result.result or {}).get("data") or result.result
            if isinstance(data, dict):
                status_str = str(data.get("status", data.get("order_status", status_str)))
                filled = bool(data.get("filled", filled))
        if status_str in ("2", "filled", "FILLED", "2.0"):
            filled = True
        return {"success": True, "filled": filled, "status": status_str, "raw": result}
    except Exception as e:
        logger.warning("get_order_status error: %s", e)
        return {"success": False, "filled": False, "status": "error", "error": str(e)}
