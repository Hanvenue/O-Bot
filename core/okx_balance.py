"""
OKX Wallet API 연동 - 지갑 주소별 USDT 잔액 조회

- OKX Web3 API 키가 있으면: OKX balance-by-address 사용
- 없으면: BSC 공개 RPC로 USDT(ERC20) balanceOf 호출 (BNB Chain 기준)
"""
import logging
import os
import time
import hmac
import hashlib
import base64
from typing import Optional, Tuple
import requests

logger = logging.getLogger(__name__)

# BSC 메인넷 USDT 컨트랙트 (Tether USD)
BSC_USDT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
# balanceOf(address) selector: first 4 bytes of keccak256("balanceOf(address)")
BALANCE_OF_SELECTOR = "0x70a08231"
# BSC 공개 RPC (무료, rate limit 있음)
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed1.binance.org/")
# OKX API base
OKX_WEB3_BASE = "https://web3.okx.com"
# BSC chain id (OKX)
CHAIN_ID_BSC = 56


def _get_okx_credentials():
    """OKX Web3 API 키가 설정돼 있으면 (key, secret, passphrase) 반환, 없으면 None."""
    key = (os.getenv("OKX_WEB3_API_KEY") or "").strip()
    secret = (os.getenv("OKX_WEB3_SECRET_KEY") or "").strip()
    passphrase = (os.getenv("OKX_WEB3_PASSPHRASE") or "").strip()
    if key and secret and passphrase:
        return (key, secret, passphrase)
    return None


def _okx_sign(secret_key: str, timestamp: str, method: str, path_with_query: str, body: str = "") -> str:
    """OKX 요청 서명 (HMAC-SHA256, Base64)."""
    prehash = timestamp + method + path_with_query + body
    sig = hmac.new(secret_key.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(sig).decode("utf-8")


def _fetch_usdt_via_okx(address: str, proxies: Optional[dict] = None) -> Optional[float]:
    """
    OKX Wallet API로 해당 주소의 토큰 잔액 조회 후 USDT만 합산.
    실패 시 None 반환.
    """
    creds = _get_okx_credentials()
    if not creds:
        return None
    api_key, secret_key, passphrase = creds
    url = f"{OKX_WEB3_BASE}/api/v5/wallet/asset/all-token-balances-by-address"
    params = {"address": address, "chains": f"{CHAIN_ID_BSC}", "filter": "1"}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    path_with_query = f"/api/v5/wallet/asset/all-token-balances-by-address?{query}"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    sign = _okx_sign(secret_key, timestamp, "GET", path_with_query)
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(url, params=params, headers=headers, proxies=proxies or {}, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "0":
            logger.warning("OKX balance API error: %s", data.get("msg", data))
            return None
        total_usdt = 0.0
        for item in data.get("data") or []:
            for asset in item.get("tokenAssets") or []:
                if (asset.get("symbol") or "").upper() == "USDT":
                    try:
                        total_usdt += float(asset.get("balance") or 0)
                    except (TypeError, ValueError):
                        pass
        # 0 USDT도 유효한 잔고이므로 0.0 반환 (total_usdt is not None 일 때만)
        return total_usdt if total_usdt is not None else None
    except Exception as e:
        logger.warning("OKX balance fetch failed for %s: %s", address[:10], e)
        return None


def _fetch_usdt_via_bsc_rpc(address: str, proxies: Optional[dict] = None) -> Optional[float]:
    """
    BSC 공개 RPC로 USDT(ERC20) balanceOf 호출.
    address는 0x 패딩 32바이트로 eth_call에 넣음.
    """
    if not address or not address.startswith("0x"):
        return None
    # ABI: address is 32 bytes, left-padded with zeros (24 zeros + 20-byte address)
    addr_hex = "0" * 24 + address[2:].lower() if len(address) >= 42 else ""
    if len(addr_hex) != 64:
        return None
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [
            {
                "to": BSC_USDT_ADDRESS,
                "data": BALANCE_OF_SELECTOR + addr_hex,
            },
            "latest",
        ],
    }
    try:
        r = requests.post(BSC_RPC_URL, json=payload, proxies={}, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data.get("result")
        if not result or result == "0x":
            return 0.0
        raw = int(result, 16)
        # BSC USDT 18 decimals
        return raw / 1e18
    except Exception as e:
        logger.warning("BSC RPC balance fetch failed for %s: %s", address[:10], e)
        return None


def get_usdt_balance_for_address(
    address: Optional[str],
    proxies: Optional[dict] = None,
    use_okx_first: bool = True,
) -> Optional[float]:
    """
    해당 지갑 주소의 BNB Chain(BSC) USDT 잔액을 반환.

    - use_okx_first True이고 OKX API 키가 있으면 OKX API 사용.
    - 그 외에는 BSC 공개 RPC로 USDT balanceOf 사용.

    Returns:
        USDT 잔액(float) 또는 조회 실패/미설정 시 None.
    """
    balance, _ = get_usdt_balance_with_reason(address, proxies, use_okx_first)
    return balance


def get_usdt_balance_with_reason(
    address: Optional[str],
    proxies: Optional[dict] = None,
    use_okx_first: bool = True,
) -> Tuple[Optional[float], Optional[str]]:
    """
    잔액 조회 + 실패 시 사유 문자열.
    Returns:
        (잔액, None) 성공 시
        (None, "사유") 실패 시 (API 응답 실패/네트워크/주소 형식 등)
    """
    if not address or not isinstance(address, str):
        return None, "지갑 주소 없음"
    address = address.strip()
    if not address.startswith("0x"):
        return None, "지갑 주소 형식 오류(0x로 시작해야 함)"
    if len(address) != 42:
        return None, "지갑 주소 길이 오류(42자)"

    if use_okx_first and _get_okx_credentials():
        value, reason = _fetch_usdt_via_okx_with_reason(address, proxies)
        if value is not None:
            return value, None
        # OKX 실패 시 BSC로 폴백
        value_bsc, reason_bsc = _fetch_usdt_via_bsc_rpc_with_reason(address, proxies)
        if value_bsc is not None:
            return value_bsc, None
        return None, reason or reason_bsc or "OKX 및 BSC 조회 모두 실패"

    value, reason = _fetch_usdt_via_bsc_rpc_with_reason(address, proxies)
    if value is not None:
        return value, None
    return None, reason or "BSC RPC 조회 실패"


def _fetch_usdt_via_okx_with_reason(address: str, proxies: Optional[dict] = None) -> Tuple[Optional[float], Optional[str]]:
    """OKX 조회. (잔액, None) 또는 (None, 실패사유)."""
    creds = _get_okx_credentials()
    if not creds:
        return None, "OKX API 키 미설정"
    api_key, secret_key, passphrase = creds
    url = f"{OKX_WEB3_BASE}/api/v5/wallet/asset/all-token-balances-by-address"
    params = {"address": address, "chains": f"{CHAIN_ID_BSC}", "filter": "1"}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    path_with_query = f"/api/v5/wallet/asset/all-token-balances-by-address?{query}"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    sign = _okx_sign(secret_key, timestamp, "GET", path_with_query)
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(url, params=params, headers=headers, proxies=proxies or {}, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "0":
            msg = data.get("msg") or data.get("message") or str(data.get("code", ""))
            reason = f"OKX API 응답 오류(code={data.get('code')}, msg={msg})"
            logger.warning("OKX balance API error: %s", reason)
            return None, reason
        total_usdt = 0.0
        for item in data.get("data") or []:
            for asset in item.get("tokenAssets") or []:
                if (asset.get("symbol") or "").upper() == "USDT":
                    try:
                        total_usdt += float(asset.get("balance") or 0)
                    except (TypeError, ValueError):
                        pass
        return total_usdt, None
    except requests.exceptions.Timeout:
        logger.warning("OKX balance timeout for %s", address[:10])
        return None, "OKX API 요청 시간 초과"
    except requests.exceptions.ProxyError as e:
        logger.warning("OKX balance proxy error for %s: %s", address[:10], e)
        return None, "OKX API 프록시 오류"
    except Exception as e:
        logger.warning("OKX balance fetch failed for %s: %s", address[:10], e)
        return None, f"OKX API 오류: {type(e).__name__}"


def _fetch_usdt_via_bsc_rpc_with_reason(address: str, proxies: Optional[dict] = None) -> Tuple[Optional[float], Optional[str]]:
    """BSC RPC 조회. (잔액, None) 또는 (None, 실패사유)."""
    if not address or not address.startswith("0x"):
        return None, "주소 형식 오류"
    addr_hex = "0" * 24 + address[2:].lower() if len(address) >= 42 else ""
    if len(addr_hex) != 64:
        return None, "주소 길이 오류(42자 아님)"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [
            {"to": BSC_USDT_ADDRESS, "data": BALANCE_OF_SELECTOR + addr_hex},
            "latest",
        ],
    }
    try:
        r = requests.post(BSC_RPC_URL, json=payload, proxies={}, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data.get("result")
        if not result or result == "0x":
            return 0.0, None
        raw = int(result, 16)
        return raw / 1e18, None
    except requests.exceptions.Timeout:
        logger.warning("BSC RPC timeout for %s", address[:10])
        return None, "BSC RPC 요청 시간 초과"
    except requests.exceptions.ProxyError as e:
        logger.warning("BSC RPC proxy error for %s: %s", address[:10], e)
        return None, "BSC RPC 프록시 오류"
    except Exception as e:
        logger.warning("BSC RPC balance fetch failed for %s: %s", address[:10], e)
        return None, f"BSC RPC 오류: {type(e).__name__}"
