"""
BTC Price Module - Get real-time Bitcoin price from Pyth Network
"""
import requests
import logging
from config import Config

logger = logging.getLogger(__name__)


class BTCPriceService:
    """Get real-time BTC/USD price from Pyth Network"""
    
    def __init__(self):
        self.api_url = Config.PYTH_API_URL
        self.feed_id = Config.BTC_PRICE_FEED_ID
    
    def get_current_price(self):
        """
        Get current BTC/USD price
        
        Returns:
            float: Current BTC price in USD
        """
        try:
            params = {
                'ids[]': self.feed_id
            }
            
            response = requests.get(self.api_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data or len(data) == 0:
                raise ValueError("No price data returned from Pyth")
            
            # Parse Pyth response
            price_feed = data[0]
            price_data = price_feed.get('price', {})
            
            # Price is returned as integer with exponent
            price = int(price_data.get('price', 0))
            expo = int(price_data.get('expo', 0))
            
            # Calculate actual price
            btc_price = price * (10 ** expo)
            
            logger.info(f"✅ Current BTC Price: ${btc_price:,.2f}")
            
            return btc_price
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to get BTC price from Pyth: {e}")
            raise
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"❌ Failed to parse Pyth response: {e}")
            raise
    
    def get_price_gap(self, start_price):
        """
        Calculate price gap between start and current price
        
        Args:
            start_price (float): Market start price
            
        Returns:
            float: Price gap (positive = UP, negative = DOWN)
        """
        current_price = self.get_current_price()
        gap = current_price - start_price
        
        logger.info(f"📊 Price Gap: ${gap:+,.2f} (Start: ${start_price:,.2f} → Current: ${current_price:,.2f})")
        
        return gap


# Singleton instance
btc_price_service = BTCPriceService()
