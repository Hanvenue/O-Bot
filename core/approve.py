"""
EOA용 USDT Approval - Predict.fun 거래 전 필수
CTF_EXCHANGE, NEG_RISK_CTF_EXCHANGE, NEG_RISK_ADAPTER에 USDT 사용 허용
"""
import logging
from typing import Optional

from core.account import Account

logger = logging.getLogger(__name__)


def run_approve(account: Account, is_yield_bearing: bool = False) -> dict:
    """
    계정의 USDT를 Predict 컨트랙트에서 사용하도록 승인 (온체인 트랜잭션)
    가스비(BNB) 필요.

    Returns:
        {success: bool, message: str, tx_count: int, error?: str}
    """
    try:
        from predict_sdk import OrderBuilder, ChainId
    except ImportError:
        return {'success': False, 'error': 'predict-sdk not installed', 'tx_count': 0}

    pk = (account.private_key or '').strip()
    if not pk:
        return {'success': False, 'error': 'Private key required', 'tx_count': 0}
    if not pk.startswith('0x'):
        pk = '0x' + pk

    try:
        builder = OrderBuilder.make(ChainId.BNB_MAINNET, pk)
        result = builder.set_approvals(is_yield_bearing=is_yield_bearing)

        tx_count = len(result.transactions) if result.transactions else 0
        if result.success:
            logger.info(f"✅ Account {account.id} approval succeeded ({tx_count} tx)")
            return {'success': True, 'message': f'승인 완료 ({tx_count}개 트랜잭션)', 'tx_count': tx_count}

        errors = [getattr(r, 'cause', None) for r in result.transactions if not getattr(r, 'success', True)]
        err_msg = str(errors[0]) if errors and errors[0] else '승인 실패'
        logger.warning(f"⚠️ Account {account.id} approval failed: {err_msg}")
        return {'success': False, 'error': str(err_msg), 'tx_count': tx_count}

    except Exception as e:
        logger.exception(f"Approve error account={account.id}")
        err = str(e)
        if 'insufficient funds' in err.lower():
            return {'success': False, 'error': '가스비용 BNB가 부족합니다.', 'tx_count': 0}
        return {'success': False, 'error': err, 'tx_count': 0}
