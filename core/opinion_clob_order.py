"""
Opinion CLOB SDK 주문 연동
- place_limit_order: LIMIT BUY 주문 (account.api_key + account.proxy, 계정별 CLOB PK/Multisig)
- cancel_order: 주문 취소
- get_order_status: 주문 체결 상태 조회
- 에러 시 opinion_errors.interpret_opinion_api_response() 경유
"""
import base64
import logging
import os
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from core.opinion_account import OpinionAccount
from core.opinion_config import get_proxy_dict
from core.opinion_errors import interpret_opinion_api_response

logger = logging.getLogger(__name__)

# CLOB SDK용 호스트 (OpenAPI 베이스; /openapi 제외)
OPINION_CLOB_HOST = os.getenv("OPINION_CLOB_HOST", "https://proxy.opinion.trade:8443")
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
# BSC RPC 실패 시 시도할 대체 URL (쉼표 구분, 비어 있으면 아래 기본 목록 사용)
_BSC_RPC_FALLBACK_RAW = (os.getenv("BSC_RPC_FALLBACKS") or "").strip()
BSC_RPC_FALLBACKS = [u.strip() for u in _BSC_RPC_FALLBACK_RAW.split(",") if u.strip()] or [
    "https://bsc-dataseed1.binance.org/",
    "https://bsc-dataseed2.binance.org/",
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-dataseed-public.bnbchain.org",
    "https://bsc-rpc.publicnode.com",
    "https://1rpc.io/bnb",
    "https://bsc.drpc.org",
    "https://bsc.publicnode.com",
    "https://bsc-dataseed.nariox.org",
    "https://bsc-dataseed.defibit.io",
    "https://binance.nodereal.io",
    "https://bsc-mainnet.public.blastapi.io",
]


def _set_rpc_proxy_env(account: OpinionAccount) -> None:
    """BSC RPC가 프록시로 나가도록 HTTP_PROXY/HTTPS_PROXY 설정 (SDK 내부 Web3/requests 사용 시)."""
    if os.getenv("BSC_RPC_USE_PROXY", "1").strip() == "0":
        return
    proxy_dict = get_proxy_dict(account.proxy or "")
    if not proxy_dict:
        return
    url = proxy_dict.get("https") or proxy_dict.get("http")
    if url:
        os.environ["HTTPS_PROXY"] = url
        os.environ["HTTP_PROXY"] = url


def _get_clob_credentials(account: OpinionAccount) -> Optional[tuple]:
    """
    계정별 CLOB 전용 private_key, multi_sig_addr 반환.
    .env: OPINION_CLOB_PK_{id} 필수.
    OPINION_MULTISIG_{id}: Opinion.trade Gnosis Safe 컨트랙트 주소(EOA 아님). 미설정 시 CLOB PK 파생 EOA 사용.
    에러 10603 시: .env에 OPINION_MULTISIG_{id}=<Safe 주소> 또는 app.opinion.trade에서 같은 지갑 연결. (docs/OPINION_ERROR_10603.md)
    """
    aid = getattr(account, "id", 1)
    pk = (os.getenv(f"OPINION_CLOB_PK_{aid}") or "").strip()
    if not pk:
        return None
    multi_sig = (os.getenv(f"OPINION_MULTISIG_{aid}") or "").strip()
    if not multi_sig:
        # .env에 적힌 계정 EOA와 동일한 문자열 사용 (10603 방지). 없으면 PK에서 파생.
        multi_sig = (getattr(account, "eoa", None) or "").strip()
        if not multi_sig:
            try:
                from eth_account import Account as EthAccount
                multi_sig = EthAccount.from_key(pk).address
            except Exception as e:
                logger.warning("CLOB PK에서 EOA 파생 실패: %s", e)
        if multi_sig:
            logger.info(
                "계정 %s: OPINION_MULTISIG_%s 미설정 → account.eoa/PK 파생 EOA 사용.",
                aid, aid,
            )
    if not multi_sig:
        return None
    if not multi_sig.startswith("0x"):
        multi_sig = "0x" + multi_sig
    # Opinion 백엔드 대소문자 비교 이슈 방지: 항상 소문자로 통일
    multi_sig = multi_sig.lower()
    return (pk, multi_sig)


def get_clob_debug_info(account: OpinionAccount) -> Optional[Dict[str, Any]]:
    """
    10603 디버깅: 지금 이 계정으로 주문 시 보내는 multi_sig_addr(마스킹) 등.
    .env의 OPINION_MULTISIG가 비어 있으면 account.eoa 또는 PK 파생 EOA 사용.
    """
    creds = _get_clob_credentials(account)
    if not creds:
        return None
    _, multi_sig_addr = creds
    eoa = (getattr(account, "eoa", None) or "").strip() or None
    aid = getattr(account, "id", 1)
    env_multisig = (os.getenv(f"OPINION_MULTISIG_{aid}") or "").strip()

    def _mask(addr: Optional[str]) -> str:
        if not addr or len(addr) < 12:
            return addr or "—"
        return (addr or "")[:8] + "..." + (addr or "")[-6:]

    proxy_configured = bool(get_proxy_dict(account.proxy or ""))
    return {
        "account_id": aid,
        "multi_sig_addr_sent": _mask(multi_sig_addr),
        "eoa_from_account": _mask(eoa),
        "opination_multisig_set": bool(env_multisig),
        "proxy_configured": proxy_configured,
        "hint": "app.opinion.trade My Profile에 보이는 주소가 multi_sig_addr_sent와 같아야 합니다.",
        "hint_10403": "10403이면 proxy_configured가 true인지, 서버 로그에 '프록시 적용됨'이 나오는지 확인하세요.",
    }


def _get_clob_client(
    account: OpinionAccount,
    multi_sig_override: Optional[str] = None,
    rpc_url_override: Optional[str] = None,
):
    """
    Opinion CLOB SDK Client 생성.
    account.api_key, account.proxy 사용. 프록시는 Configuration.proxy + RESTClient 재생성으로 주입 (레이스 컨디션 방지).
    multi_sig_override: 지정 시 이 주소를 multi_sig_addr로 사용 (10603 재시도 시 EOA 강제용).
    rpc_url_override: 지정 시 이 URL을 BSC RPC로 사용 (RPC 실패 시 대체 RPC 재시도용).
    """
    creds = _get_clob_credentials(account)
    if not creds:
        return None
    private_key, multi_sig_addr = creds
    if multi_sig_override:
        multi_sig_addr = (multi_sig_override or "").strip()
        if multi_sig_addr and not multi_sig_addr.startswith("0x"):
            multi_sig_addr = "0x" + multi_sig_addr
        # 소문자/checksummed 그대로 전달 (재시도 시 둘 다 시도)
        logger.info("CLOB client multi_sig_override 적용 (10603 재시도): %s...%s", (multi_sig_addr or "")[:8], (multi_sig_addr or "")[-4:])
    rpc_url = (rpc_url_override or BSC_RPC_URL).strip() or BSC_RPC_URL
    _set_rpc_proxy_env(account)
    # 10603 디버깅: 사용 중인 자산 주소 로그 (마스킹)
    _mask_addr = (multi_sig_addr or "")[:8] + "..." + (multi_sig_addr or "")[-4:] if (multi_sig_addr or "") else "?"
    logger.info("CLOB client 계정 id=%s, multi_sig_addr=%s, rpc=%s", getattr(account, "id", 1), _mask_addr, (rpc_url[:40] + "..." if len(rpc_url) > 40 else rpc_url))
    try:
        from opinion_clob_sdk import Client
    except ImportError as e:
        logger.warning("opinion_clob_sdk import failed: %s", e)
        return None

    client = Client(
        host=OPINION_CLOB_HOST,
        apikey=account.api_key,
        chain_id=56,
        rpc_url=rpc_url,
        private_key=private_key,
        multi_sig_addr=multi_sig_addr,
    )

    proxy_dict = get_proxy_dict(account.proxy or "")
    if proxy_dict and hasattr(client, "api_client") and client.api_client is not None:
        conf = client.api_client.configuration
        proxy_url = proxy_dict.get("https") or proxy_dict.get("http")
        if proxy_url and conf is not None:
            # Configuration에 먼저 설정한 뒤, RESTClientObject를 새로 만들어야 프록시가 적용됨 (생성 시 conf.proxy 읽음)
            conf.proxy = proxy_url
            parsed = urlparse(proxy_url)
            proxy_host = (parsed.hostname or parsed.path or "?") if parsed else "?"
            # HTTPS CONNECT 터널링 시 Proxy-Authorization 헤더 전송 (407 방지)
            if parsed.username and parsed.password:
                credentials = base64.b64encode(
                    f"{parsed.username}:{parsed.password}".encode()
                ).decode()
                conf.proxy_headers = {"Proxy-Authorization": f"Basic {credentials}"}
            try:
                from opinion_api.rest import RESTClientObject
                client.api_client.rest_client = RESTClientObject(conf)
                logger.info(
                    "CLOB 계정 id=%s: 프록시 적용됨 (host=%s). 주문 요청은 이 프록시를 통해 나갑니다. 10403이면 이 IP가 제한 지역인지 확인하세요.",
                    getattr(account, "id", 1),
                    proxy_host,
                )
            except Exception as e:
                logger.warning("CLOB RESTClient proxy 주입 실패 (주문 요청이 프록시 없이 나갈 수 있음): %s", e)
    else:
        if not proxy_dict:
            logger.warning("CLOB 계정 id=%s: 프록시 없음. 주문 요청이 서버 IP로 나가므로 10403(지역 제한) 가능성 있음.", getattr(account, "id", 1))

    return client


def _place_order_impl(
    account: OpinionAccount,
    market_id: int,
    token_id: str,
    side: str,
    price: float,
    size: int,
    order_type_name: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    내부 공통: LIMIT 또는 MARKET 주문.
    order_type_name: "LIMIT_ORDER" | "MARKET_ORDER"
    """
    try:
        from opinion_clob_sdk.chain.py_order_utils.model.order import PlaceOrderDataInput
        from opinion_clob_sdk.chain.py_order_utils.model.sides import OrderSide
        from opinion_clob_sdk.chain.py_order_utils.model.order_type import LIMIT_ORDER, MARKET_ORDER
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
            "error": "CLOB 주문을 위해 해당 계정의 OPINION_CLOB_PK_{id}를 .env에 설정해 주세요. (MULTISIG 없으면 EOA 사용)",
            "needs_clob": True,
            "order_id": None,
        }

    side_val = OrderSide.BUY if (side or "BUY").strip().upper() == "BUY" else OrderSide.SELL
    amount_quote = max(1.0, float(price) * max(1, int(size)))
    order_type = MARKET_ORDER if order_type_name == "MARKET_ORDER" else LIMIT_ORDER
    # MARKET 주문 시 SDK에 넘기는 price는 1.0(슬리피지 상한 최대). amount_quote는 원래 price 기준 유지.
    sdk_price = "1.0" if order_type_name == "MARKET_ORDER" else str(round(float(price), 2))
    # makerAmountInQuoteToken must be at least 1 (USDT). 정수로 올려서 전달.
    amount_str = str(max(1, int(round(amount_quote))))

    try:
        data = PlaceOrderDataInput(
            marketId=int(market_id),
            tokenId=(token_id or "").strip(),
            side=side_val,
            orderType=order_type,
            price=sdk_price,
            makerAmountInQuoteToken=amount_str,
        )
        # check_approval=True: SDK가 enable_trading() 자동 실행 → USDT 사용 승인 트랜잭션
        result = client.place_order(data, check_approval=True)
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
        logger.exception("place order error: %s", err_msg)
        logger.warning("place order raw exception type=%s repr=%s", type(e).__name__, repr(e)[:500])
        # 10603: body에 code로 올 수도 있음 (SDK 래핑 방식에 따라 str(e)에 없을 수 있음)
        body = getattr(e, "body", None) if hasattr(e, "body") else None
        is_10603 = "10603" in err_msg or (isinstance(body, dict) and body.get("code") == 10603)
        if is_10603 and isinstance(body, dict):
            logger.warning("10603 응답 body (기대 주소 확인용): %s", body)
        # 10603: MULTISIG 불일치 → EOA만으로 재시도 (소문자 → checksummed 순으로 시도)
        if is_10603:
            try:
                from eth_account import Account as EthAccount
                aid = getattr(account, "id", 1)
                pk = (os.getenv(f"OPINION_CLOB_PK_{aid}") or "").strip()
                if pk:
                    eoa = EthAccount.from_key(pk).address  # checksummed
                    for addr in (eoa.lower(), eoa):  # 소문자 먼저, 실패 시 checksummed
                        retry_client = _get_clob_client(account, multi_sig_override=addr)
                        if not retry_client:
                            continue
                        try:
                            result = retry_client.place_order(data, check_approval=True)
                            order_id = None
                            if hasattr(result, "result") and hasattr(result.result, "data"):
                                data_obj = result.result.data
                                order_id = getattr(data_obj, "order_id", None) or getattr(data_obj, "id", None)
                            if order_id is None and hasattr(result, "result"):
                                r = result.result
                                order_id = getattr(r, "order_id", None) or (isinstance(getattr(r, "data", None), dict) and (r.data or {}).get("order_id") or (r.data or {}).get("id"))
                            if order_id is None and isinstance(result, dict):
                                order_id = result.get("order_id") or result.get("id")
                            if order_id is not None:
                                logger.info("10603 재시도(EOA %s) 성공 order_id=%s", "lower" if addr == eoa.lower() else "checksum", order_id)
                                return {"success": True, "order_id": str(order_id), "id": order_id}
                        except Exception as retry_e:
                            logger.warning("10603 재시도 addr=%s... 실패: %s", (addr or "")[:10], retry_e)
            except Exception as outer_e:
                logger.warning("10603 EOA 재시도 준비 실패: %s", outer_e)
            err_msg = (
                "10603: Opinion이 기대하는 지갑 주소와 다릅니다. "
                "해결: app.opinion.trade 접속 → 로그인(CLOB PK와 같은 지갑) → My Profile에서 보이는 지갑 주소를 복사 → .env에 OPINION_MULTISIG_1=(그 주소) 넣고 저장 → 서버 재시작(README '운영 시 자주 쓰는 명령어') 후 다시 시도. "
                "서버 로그에 '10603 응답 body'가 남으니 필요 시 확인."
            )
        elif "contract" in err_msg.lower() and ("chain synced" in err_msg.lower() or "transact with" in err_msg.lower()):
            # BSC RPC 실패 → 대체 RPC로 자동 재시도 (기본 URL은 이미 실패했으므로 fallback만 시도)
            for fallback_url in BSC_RPC_FALLBACKS:
                if (fallback_url or "").strip() == (BSC_RPC_URL or "").strip():
                    continue
                try:
                    retry_client = _get_clob_client(account, rpc_url_override=fallback_url)
                    if not retry_client:
                        continue
                    result = retry_client.place_order(data, check_approval=True)
                    order_id = None
                    if hasattr(result, "result") and hasattr(result.result, "data"):
                        data_obj = result.result.data
                        order_id = getattr(data_obj, "order_id", None) or getattr(data_obj, "id", None)
                    if order_id is None and hasattr(result, "result"):
                        r = result.result
                        order_id = getattr(r, "order_id", None) or (isinstance(getattr(r, "data", None), dict) and (r.data or {}).get("order_id") or (r.data or {}).get("id"))
                    if order_id is None and isinstance(result, dict):
                        order_id = result.get("order_id") or result.get("id")
                    if order_id is not None:
                        logger.info("BSC RPC fallback 성공 rpc=%s... order_id=%s", fallback_url[:50], order_id)
                        return {"success": True, "order_id": str(order_id), "id": order_id}
                except Exception as retry_e:
                    logger.warning("BSC RPC fallback %s 실패: %s", (fallback_url or "")[:50], retry_e)
            err_msg = (
                "BSC(이더리움) 컨트랙트 호출에 실패했습니다. 기본 RPC와 대체 RPC 모두 실패했습니다. "
                "서버에서 BSC RPC에 접속 가능한지 확인하세요. .env의 BSC_RPC_URL을 다른 공개 RPC로 바꾸거나, BSC_RPC_FALLBACKS에 추가해 보세요. "
                "일시적인 BSC/네트워크 장애일 수도 있으니 잠시 후 다시 시도해 보세요."
            )
        elif hasattr(e, "status") and hasattr(e, "body"):
            # SDK는 body를 문자열로 줄 수 있음 (JSON). interpret에서 파싱함
            body = getattr(e, "body", None)
            interpreted = interpret_opinion_api_response(
                getattr(e, "status", 500),
                body,
                context="CLOB 주문",
            )
            if interpreted.get("user_message"):
                err_msg = interpreted["user_message"]
        return {"success": False, "error": err_msg, "order_id": None}


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
    LIMIT 주문 (Maker용: 호가창에 걸어 둠).
    - market_id: Opinion marketId (topic_id).
    - side: "BUY" (SELL은 필요 시 확장).
    - price: 0.01~0.99.
    - size: 주문 수량(샤드). makerAmountInQuoteToken = price * size (USDT).
    """
    return _place_order_impl(
        account, market_id, token_id, side, price, size, "LIMIT_ORDER", **kwargs
    )


def place_market_order(
    account: OpinionAccount,
    market_id: int,
    token_id: str,
    side: str,
    price: float,
    size: int,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    MARKET 주문 (Taker용: 즉시 체결 우선).
    - 동일 market_id/token_id/price/size. 체결 지연 없이 매칭 엔진이 즉시 처리.
    - 자전거래 시 Maker LIMIT 직후 Taker를 MARKET로 보내면 반대쪽이 '바로 받아서' 체결될 가능성 확대.
    """
    return _place_order_impl(
        account, market_id, token_id, side, price, size, "MARKET_ORDER", **kwargs
    )


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
        return {"success": False, "error": "CLOB 계정 설정 없음 (OPINION_CLOB_PK_* 필요)", "needs_clob": True}

    try:
        client.cancel_order(order_id)
        return {"success": True}
    except Exception as e:
        err_msg = str(e)
        logger.warning("cancel_order error: %s", err_msg)
        if hasattr(e, "status") and hasattr(e, "body"):
            interpreted = interpret_opinion_api_response(
                getattr(e, "status", 500),
                getattr(e, "body", None),
                context="CLOB 취소",
            )
            if interpreted.get("user_message"):
                err_msg = interpreted["user_message"]
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
