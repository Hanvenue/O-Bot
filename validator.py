"""
Validator Module - Check if trade conditions are met
"""
import logging
from datetime import datetime, timezone
from config import Config
from core.btc_price import btc_price_service

logger = logging.getLogger(__name__)


class TradeValidator:
    """Validate trade conditions before execution"""
    
    @staticmethod
    def validate_market(market_data: dict, skip_time_check: bool = False) -> tuple[bool, str, str]:
        """
        Validate if market meets trade conditions
        
        Args:
            market_data: Market information from Predict.fun
            skip_time_check: If True, skip 5-min-before-end check (for manual trade)
            
        Returns:
            tuple: (is_valid, direction, reason)
                - is_valid: True if should trade
                - direction: "UP" or "DOWN"
                - reason: Explanation
        """
        try:
            # 1. Check market end time
            end_time = market_data.get('end_time')
            if not end_time:
                return False, None, "No end time"
            
            # Handle end_time as string (from JSON API)
            if isinstance(end_time, str):
                try:
                    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return False, None, "Invalid end_time format"
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            
            time_remaining = (end_time - datetime.now(timezone.utc)).total_seconds()
            
            if time_remaining < 0:
                return False, None, "Market already ended"
            
            # Skip 5-min-before-end check for manual trade
            if not skip_time_check and time_remaining > Config.TIME_BEFORE_END:
                return False, None, f"Too early: {int(time_remaining)}s remaining"
            
            logger.info(f"⏱️ Time remaining: {int(time_remaining)}s")
            
            # 2. Get BTC prices
            start_price = market_data.get('start_price')
            if not start_price:
                return False, None, "No start price"
            
            price_gap = btc_price_service.get_price_gap(start_price)
            
            # 3. Check price gap (±$200)
            if abs(price_gap) < Config.MIN_PRICE_GAP:
                return False, None, f"Gap insufficient: ${price_gap:+,.2f} (need ±${Config.MIN_PRICE_GAP})"
            
            # 4. Determine direction
            if price_gap >= Config.MIN_PRICE_GAP:
                direction = "UP"
                logger.info(f"✅ Trade condition met: UP (+${price_gap:,.2f})")
            else:
                direction = "DOWN"
                logger.info(f"✅ Trade condition met: DOWN (${price_gap:,.2f})")
            
            return True, direction, f"Ready to trade {direction}"
            
        except Exception as e:
            logger.error(f"❌ Validation error: {e}")
            return False, None, str(e)
    
    @staticmethod
    def validate_orderbook(orderbook: dict, direction: str) -> tuple[bool, float]:
        """
        Validate orderbook and get optimal price
        
        Args:
            orderbook: Orderbook data
            direction: "UP" or "DOWN"
            
        Returns:
            tuple: (is_valid, optimal_price)
        """
        try:
            def _extract_price(level):
                """Extract price from [price, qty] or {price: x, amount: y}"""
                if isinstance(level, (list, tuple)) and len(level) >= 1:
                    return float(level[0])
                if isinstance(level, dict):
                    val = level.get('price') or level.get('size') or level.get('amount')
                    return float(val) if val is not None else None
                return None
            
            if direction == "UP":
                asks = orderbook.get('asks', [])
                if not asks:
                    return False, None
                best_ask = _extract_price(asks[0])
                if best_ask is None:
                    return False, None
                optimal_price = max(0.01, best_ask - 0.01)
                logger.info(f"📊 UP - Best Ask: ${best_ask:.2f} → Maker: ${optimal_price:.2f}")
            else:  # DOWN
                bids = orderbook.get('bids', [])
                if not bids:
                    return False, None
                best_bid = _extract_price(bids[0])
                if best_bid is None:
                    return False, None
                optimal_price = max(0.01, best_bid - 0.01)
                logger.info(f"📊 DOWN - Best Bid: ${best_bid:.2f} → Maker: ${optimal_price:.2f}")
            
            return True, optimal_price
            
        except Exception as e:
            logger.error(f"❌ Orderbook validation error: {e}")
            return False, None


# Singleton
trade_validator = TradeValidator()
