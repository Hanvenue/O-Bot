"""
Trader Module - Execute wash trades (Maker-Taker strategy)
계정별 프록시 사용하여 Predict.fun 실거래 실행
"""
import logging
import time
from typing import Optional
from core.account import Account
from core.predict_order import submit_order, cancel_orders

logger = logging.getLogger(__name__)


class Trader:
    """Execute trades on Predict.fun (proxy per account)"""
    
    def __init__(self, predict_client=None):
        self.client = predict_client
    
    def execute_wash_trade(
        self,
        market_id: int,
        maker_account: Account,
        taker_account: Account,
        direction: str,
        maker_price: float,
        shares: int
    ) -> dict:
        """
        Execute wash trade (자전거래)
        
        Args:
            market_id: Market ID
            maker_account: Account for Maker order (no fee)
            taker_account: Account for Taker order (with fee)
            direction: "UP" or "DOWN"
            maker_price: Price for Maker order
            shares: Number of shares
            
        Returns:
            dict: Trade result
        """
        try:
            logger.info(f"🚀 Starting wash trade...")
            logger.info(f"   Maker: Account {maker_account.id} → {direction} ${maker_price:.2f} × {shares}")
            logger.info(f"   Taker: Account {taker_account.id} → {'DOWN' if direction == 'UP' else 'UP'}")
            
            # Step 1: Place Maker order (limit order, no fee)
            maker_result = self._place_maker_order(
                market_id=market_id,
                account=maker_account,
                side=direction,
                price=maker_price,
                shares=shares
            )
            
            if not maker_result.get('success'):
                return {
                    'success': False,
                    'error': f"Maker order failed: {maker_result.get('error', 'Unknown')}"
                }
            
            logger.info(f"✅ Maker order placed: {maker_result.get('order_hash', 'N/A')}")
            
            # Wait for order to be in orderbook
            time.sleep(2)
            
            # Step 2: Place Taker order (opposite side)
            opposite_side = "DOWN" if direction == "UP" else "UP"
            opposite_price = 1.0 - maker_price  # YES + NO = $1.00
            
            taker_result = self._place_taker_order(
                market_id=market_id,
                account=taker_account,
                side=opposite_side,
                price=opposite_price,
                shares=shares
            )
            
            if not taker_result.get('success'):
                self._cancel_order(maker_account, maker_result.get('order_hash', ''))
                return {
                    'success': False,
                    'error': f"Taker order failed: {taker_result.get('error')}"
                }
            
            logger.info(f"✅ Taker order placed: {taker_result.get('order_hash', 'N/A')}")
            
            # Success
            return {
                'success': True,
                'maker_order': maker_result.get('order_hash'),
                'taker_order': taker_result.get('order_hash'),
                'direction': direction,
                'price': maker_price,
                'shares': shares
            }
            
        except Exception as e:
            logger.error(f"❌ Wash trade failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _place_maker_order(self, market_id: int, account: Account, side: str, price: float, shares: int) -> dict:
        """Place Maker (limit) order - 계정 프록시 사용"""
        return submit_order(
            account=account,
            market_id=market_id,
            side=side,
            price_per_share=price,
            shares=shares,
            strategy='LIMIT',
        )
    
    def _place_taker_order(self, market_id: int, account: Account, side: str, price: float, shares: int) -> dict:
        """Place Taker (limit) order - 계정 프록시 사용. Taker는 반대편 호가에 매칭."""
        return submit_order(
            account=account,
            market_id=market_id,
            side=side,
            price_per_share=price,
            shares=shares,
            strategy='LIMIT',
        )
    
    def _cancel_order(self, account: Account, order_hash: str):
        """Remove order from orderbook (계정 JWT 사용)"""
        if not order_hash:
            return
        try:
            result = cancel_orders(account, [order_hash])
            if result.get('success'):
                logger.info(f"✅ Order removed: {order_hash}")
            else:
                logger.warning(f"⚠️ Cancel failed for {order_hash}: {result.get('error')}")
        except Exception as e:
            logger.error(f"❌ Cancel error: {e}")


# Will be initialized in app.py with actual Predict client
trader = None
