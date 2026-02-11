"""
Opinion OpenAPI 클라이언트 (프록시·API키 지원)
"""
import logging
from typing import Optional, Dict, Any

import requests

from core.opinion_config import (
    OPINION_API_BASE,
    OPINION_API_KEY,
    get_proxy_dict,
    has_proxy,
)

logger = logging.getLogger(__name__)


def _headers(api_key: str) -> dict:
    return {
        "apikey": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(
    method: str,
    path: str,
    api_key: str,
    proxy_str: Optional[str] = None,
    params: Optional[dict] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """공통 요청. path는 /openapi 제외한 부분 (예: /positions/user/0x...)."""
    url = f"{OPINION_API_BASE.rstrip('/')}{path}"
    headers = _headers(api_key)
    proxies = get_proxy_dict(proxy_str) if proxy_str else None
    try:
        r = requests.request(
            method, url, headers=headers, params=params, proxies=proxies, timeout=timeout
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        # 성공: 문서는 code===0, 실제 API는 errno===0 둘 다 허용
        code_ok = data.get("code") == 0 or data.get("code") is None
        errno_ok = data.get("errno") == 0
        ok = r.ok and (code_ok or errno_ok)
        return {"status_code": r.status_code, "data": data, "ok": ok}
    except Exception as e:
        logger.exception("Opinion API request error: %s", e)
        return {"status_code": -1, "data": {}, "ok": False, "error": str(e)}


def get_positions(
    wallet_address: str,
    api_key: str,
    proxy_str: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """GET /positions/user/{walletAddress}"""
    addr = wallet_address.strip()
    if not addr.startswith("0x"):
        addr = "0x" + addr
    path = f"/positions/user/{addr}"
    return _request("GET", path, api_key, proxy_str, params={"page": page, "limit": limit})


def get_trades(
    wallet_address: str,
    api_key: str,
    proxy_str: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """GET /trade/user/{walletAddress}"""
    addr = wallet_address.strip()
    if not addr.startswith("0x"):
        addr = "0x" + addr
    path = f"/trade/user/{addr}"
    return _request("GET", path, api_key, proxy_str, params={"page": page, "limit": limit})


def get_markets(
    api_key: str,
    proxy_str: Optional[str] = None,
    status: str = "activated",
    sort_by: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """GET /market (목록). sortBy=5 → 24h 거래량 순."""
    params = {"status": status, "page": page, "limit": limit}
    if sort_by is not None:
        params["sortBy"] = sort_by
    return _request("GET", "/market", api_key, proxy_str, params=params)


def get_market(
    market_id: int,
    api_key: str,
    proxy_str: Optional[str] = None,
) -> Dict[str, Any]:
    """GET /market/{marketId} (시장 상세)"""
    return _request("GET", f"/market/{market_id}", api_key, proxy_str)


def get_latest_price(
    token_id: str,
    api_key: str,
    proxy_str: Optional[str] = None,
) -> Dict[str, Any]:
    """GET /token/latest-price?token_id=..."""
    return _request(
        "GET", "/token/latest-price", api_key, proxy_str, params={"token_id": token_id}
    )


def get_orderbook(
    token_id: str,
    api_key: str,
    proxy_str: Optional[str] = None,
) -> Dict[str, Any]:
    """GET /token/orderbook?token_id=..."""
    return _request(
        "GET", "/token/orderbook", api_key, proxy_str, params={"token_id": token_id}
    )


def get_price_history(
    token_id: str,
    api_key: str,
    proxy_str: Optional[str] = None,
    interval: str = "1d",
) -> Dict[str, Any]:
    """GET /token/price-history?token_id=...&interval=1d"""
    return _request(
        "GET",
        "/token/price-history",
        api_key,
        proxy_str,
        params={"token_id": token_id, "interval": interval},
    )


def get_quote_tokens(
    api_key: str,
    proxy_str: Optional[str] = None,
) -> Dict[str, Any]:
    """GET /quoteToken (거래 통화 목록)"""
    return _request("GET", "/quoteToken", api_key, proxy_str)
