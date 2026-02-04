"""
Predict.fun JWT Auth & 연결 계정 (name, points 등)
https://dev.predict.fun/get-connected-account-25326917e0
"""
import logging
import time
import requests
from typing import Optional, Dict, List, Any
from eth_account import Account as EthAccount
from eth_account.messages import encode_defunct

from config import Config
from core.account import Account

logger = logging.getLogger(__name__)

_JWT_CACHE: Dict[int, tuple] = {}
_JWT_BUFFER_SEC = 300


def _sanitize_api_key(key) -> str:
    if not key:
        return ''
    return ''.join(c for c in str(key).strip() if ord(c) < 128 and (c.isalnum() or c in '-'))


def _base_url() -> str:
    return (Config.PREDICT_BASE_URL or 'https://api.predict.fun').rstrip('/')


def get_auth_message(api_key: Optional[str] = None) -> Optional[str]:
    """GET /v1/auth/message"""
    api_key = _sanitize_api_key(api_key or Config.PREDICT_API_KEY)
    if not api_key:
        return None
    url = f"{_base_url()}/v1/auth/message"
    try:
        r = requests.get(url, headers={'x-api-key': api_key}, timeout=15)
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.ok and body.get('success'):
            return (body.get('data') or {}).get('message')
        return None
    except Exception as e:
        logger.exception("get_auth_message error")
        return None


def get_jwt_for_account(account: Account, api_key: Optional[str] = None, force_refresh: bool = False) -> Optional[str]:
    """계정별 JWT 발급 (캐시, 프록시 사용)"""
    api_key = _sanitize_api_key(api_key or Config.PREDICT_API_KEY)
    if not api_key:
        return None
    if not force_refresh and account.id in _JWT_CACHE:
        token, expires = _JWT_CACHE[account.id]
        if expires > time.time() + _JWT_BUFFER_SEC:
            return token
    message = get_auth_message(api_key)
    if not message:
        return None
    try:
        eth_acc = EthAccount.from_key(account.private_key)
        signable = encode_defunct(text=message)
        signed = eth_acc.sign_message(signable)
        sig_hex = signed.signature.hex()
        if not sig_hex.startswith('0x'):
            sig_hex = '0x' + sig_hex
        url = f"{_base_url()}/v1/auth"
        payload = {'signer': eth_acc.address, 'signature': sig_hex, 'message': message}
        headers = {'x-api-key': api_key, 'Content-Type': 'application/json'}
        proxies = None
        if getattr(account, 'proxy', None) and ':' in str(account.proxy):
            try:
                proxies = account.get_proxy_dict()
            except (ValueError, AttributeError):
                pass
        r = requests.post(url, json=payload, headers=headers, proxies=proxies, timeout=15)
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.ok and body.get('success'):
            token = (body.get('data') or {}).get('token')
            if token:
                _JWT_CACHE[account.id] = (token, time.time() + 3600)
                return token
        return None
    except Exception as e:
        logger.exception(f"get_jwt_for_account error account={account.id}")
        return None


def get_connected_account(jwt_token: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """GET /v1/account - Predict.fun 연결 계정 (name, address, points 등)"""
    api_key = _sanitize_api_key(api_key or Config.PREDICT_API_KEY)
    if not api_key or not jwt_token:
        return None
    url = f"{_base_url()}/v1/account"
    headers = {'x-api-key': api_key, 'Authorization': f'Bearer {jwt_token}', 'Content-Type': 'application/json'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.ok and body.get('success'):
            return body.get('data') or {}
        return None
    except Exception as e:
        logger.exception("get_connected_account error")
        return None


def get_predict_account_for_account(account: Account, api_key: Optional[str] = None) -> dict:
    """등록된 계정의 Predict 연결 정보 (name, points 등) 조회"""
    jwt_token = get_jwt_for_account(account, api_key)
    if not jwt_token:
        return {'success': False, 'error': 'JWT 발급 실패'}
    data = get_connected_account(jwt_token, api_key)
    if not data:
        return {'success': False, 'error': 'Predict 계정 조회 실패'}
    return {'success': True, 'data': data}
