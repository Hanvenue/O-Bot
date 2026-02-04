"""
Predict.fun Order Client - 주문 생성·서명·제출 (계정별 프록시 사용)
https://dev.predict.fun/create-an-order-25326903e0
"""
import logging
import time
import requests
from typing import Optional

from config import Config
from core.account import Account
from core.market import market_service

logger = logging.getLogger(__name__)

# 18 decimals
WEI = 10**18


def _sanitize_api_key(key):
    if not key:
        return ''
    return ''.join(c for c in str(key).strip() if ord(c) < 128 and (c.isalnum() or c in '-'))


def _get_market_trading_info(market_id: int) -> Optional[dict]:
    """Fetch full market for token_id, fee_rate_bps, is_neg_risk, is_yield_bearing."""
    full = market_service._fetch_market_by_id(market_id)
    if not full:
        return None
    outcomes = full.get('outcomes') or []
    fee_bps = full.get('feeRateBps', 0) or 0
    is_neg_risk = bool(full.get('isNegRisk', False))
    is_yield_bearing = bool(full.get('isYieldBearing', False))
    token_ids = {}
    for i, o in enumerate(outcomes):
        idx = o.get('indexSet', i + 1)
        tid = o.get('tokenId') or o.get('id') or o.get('onChainId')
        if tid is not None:
            s = str(tid)
            if s.startswith('0x'):
                s = s[2:]
            token_ids[idx] = s
    if not token_ids and outcomes:
        token_ids = {i + 1: str(o.get('id', i + 1)) for i, o in enumerate(outcomes) if o.get('id') is not None}
    if not token_ids:
        logger.warning(f"Market {market_id}: no token_ids in outcomes")
    return {
        'token_ids': token_ids,
        'fee_rate_bps': int(fee_bps),
        'is_neg_risk': is_neg_risk,
        'is_yield_bearing': is_yield_bearing,
    }


def _price_to_wei(price: float) -> int:
    return int(price * WEI)


def _shares_to_wei(shares: int) -> int:
    return shares * WEI


def submit_order(
    account: Account,
    market_id: int,
    side: str,
    price_per_share: float,
    shares: int,
    strategy: str = 'LIMIT',
    api_key: Optional[str] = None,
) -> dict:
    """
    Create and submit order to Predict.fun. Uses account's proxy for IP isolation.

    Args:
        account: Account (has private_key, get_proxy_dict)
        market_id: Market ID
        side: "UP" (YES) or "DOWN" (NO)
        price_per_share: 0.0–1.0
        shares: Number of shares
        strategy: "LIMIT" or "MARKET"
        api_key: Override API key (default: Config)

    Returns:
        {success, order_hash, order_id, error}
    """
    try:
        from predict_sdk import OrderBuilder, ChainId, Side, BuildOrderInput, LimitHelperInput
    except ImportError:
        return {'success': False, 'error': 'predict-sdk not installed'}

    info = _get_market_trading_info(market_id)
    if not info:
        return {'success': False, 'error': f'Market {market_id} trading info not found'}
    token_ids = info['token_ids']
    fee_bps = info['fee_rate_bps'] or 100
    is_neg_risk = info.get('is_neg_risk', False)
    is_yield_bearing = info.get('is_yield_bearing', False)

    # UP=YES=indexSet 1, DOWN=NO=indexSet 2
    token_id = token_ids.get(1) if side.upper() == 'UP' else token_ids.get(2)
    if not token_id:
        token_id = token_ids.get(list(token_ids.keys())[0]) if token_ids else None
    if not token_id:
        return {'success': False, 'error': f'Token ID not found for {side}'}

    sdk_side = Side.BUY
    price_wei = _price_to_wei(price_per_share)
    qty_wei = _shares_to_wei(shares)

    try:
        builder = OrderBuilder.make(ChainId.BNB_MAINNET, account.private_key)
        amounts = builder.get_limit_order_amounts(
            LimitHelperInput(side=sdk_side, price_per_share_wei=price_wei, quantity_wei=qty_wei)
        )
        order = builder.build_order(
            strategy,
            BuildOrderInput(
                side=sdk_side,
                token_id=token_id,
                maker_amount=str(amounts.maker_amount),
                taker_amount=str(amounts.taker_amount),
                fee_rate_bps=fee_bps,
            ),
        )
        typed_data = builder.build_typed_data(order, is_neg_risk=is_neg_risk, is_yield_bearing=is_yield_bearing)
        order_hash = builder.build_typed_data_hash(typed_data)
        signed = builder.sign_typed_data_order(typed_data)

        api_key = api_key or Config.PREDICT_API_KEY
        api_key = _sanitize_api_key(api_key)
        base = (Config.PREDICT_BASE_URL or 'https://api.predict.fun').rstrip('/')
        url = f'{base}/v1/orders'

        payload = {
            'data': {
                'pricePerShare': str(price_wei),
                'strategy': strategy,
                'order': {
                    'hash': order_hash,
                    'salt': signed.salt,
                    'maker': signed.maker,
                    'signer': signed.signer,
                    'taker': signed.taker,
                    'tokenId': str(signed.token_id),
                    'makerAmount': str(signed.maker_amount),
                    'takerAmount': str(signed.taker_amount),
                    'expiration': str(signed.expiration),
                    'nonce': str(signed.nonce),
                    'feeRateBps': str(signed.fee_rate_bps),
                    'side': int(signed.side),
                    'signatureType': int(signed.signature_type),
                    'signature': signed.signature,
                },
            }
        }

        from core.auth import get_jwt_for_account
        jwt_token = get_jwt_for_account(account, api_key)
        if not jwt_token:
            return {'success': False, 'error': 'JWT 발급 실패 - Predict 인증 필요'}

        headers = {
            'x-api-key': api_key,
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json',
        }
        proxies = None
        if getattr(account, 'proxy', None) and ':' in str(account.proxy):
            try:
                proxies = account.get_proxy_dict()
            except (ValueError, AttributeError):
                pass

        resp = requests.post(url, json=payload, headers=headers, proxies=proxies, timeout=30)
        body = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}

        if resp.status_code in (200, 201) and body.get('success'):
            data = body.get('data', {})
            oh = data.get('orderHash') or order_hash
            oid = data.get('orderId', '')
            logger.info(f"✅ Order submitted via proxy: {oh}")
            return {'success': True, 'order_hash': oh, 'order_id': oid}
        err = body.get('error') or body.get('message') or resp.text[:200]
        logger.error(f"❌ Order submit failed ({resp.status_code}): {err}")
        return {'success': False, 'error': err or f'HTTP {resp.status_code}'}

    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.exception("Order submit error")
        return {'success': False, 'error': str(e)}


def cancel_orders(account: Account, order_ids: list, api_key: Optional[str] = None) -> dict:
    """Remove orders from orderbook (계정 JWT 사용)"""
    from core.auth import remove_orders as auth_remove
    order_ids = [str(o).strip() for o in order_ids if o]
    return auth_remove(account, order_ids, api_key)
