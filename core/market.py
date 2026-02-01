"""
Market Module - Handle Predict.fun market data
"""
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, List
from config import Config

logger = logging.getLogger(__name__)


class Market:
    """Single market representation"""
    
    def __init__(self, data: dict):
        self.id = data.get('id')
        self.title = data.get('title')
        self.category = data.get('category')
        self.start_time = self._parse_time(data.get('start_time'))
        self.end_time = self._parse_time(data.get('end_time'))
        self.start_price = data.get('start_price', 0.0)
        self.current_price = data.get('current_price', 0.0)
        self.yes_price = data.get('yes_price', 0.5)
        self.no_price = data.get('no_price', 0.5)
        self.volume = data.get('volume', 0.0)
        self.resolved = data.get('resolved', False)
    
    def _parse_time(self, time_str):
        """Parse ISO time string to datetime"""
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except:
            return None
    
    def time_remaining(self):
        """Get seconds until market ends"""
        if not self.end_time:
            return 0
        delta = self.end_time - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))
    
    def price_gap(self):
        """Get price gap from start"""
        return self.current_price - self.start_price
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'start_price': self.start_price,
            'current_price': self.current_price,
            'price_gap': self.price_gap(),
            'yes_price': self.yes_price,
            'no_price': self.no_price,
            'volume': self.volume,
            'time_remaining': self.time_remaining(),
            'resolved': self.resolved
        }


class MarketService:
    """Get and filter Predict.fun markets"""
    
    def __init__(self):
        self.base_url = Config.PREDICT_BASE_URL
        self.api_key = Config.PREDICT_API_KEY
    
    def get_15min_btc_markets(self) -> List[Market]:
        """
        Get all 15-minute BTC/USD markets
        
        Returns:
            List of Market objects
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # TODO: Replace with actual Predict.fun API endpoint
            url = f"{self.base_url}/markets"
            params = {
                'category': 'crypto',
                'symbol': 'BTC',
                'duration': '15min'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            markets = [Market(m) for m in data.get('markets', [])]
            
            logger.info(f"✅ Found {len(markets)} BTC 15-min markets")
            
            return markets
            
        except Exception as e:
            logger.error(f"❌ Failed to get markets: {e}")
            return []
    
    def get_current_market(self) -> Optional[Market]:
        """
        Get the current active 15-minute market
        
        Returns:
            Market object or None
        """
        markets = self.get_15min_btc_markets()
        
        # Filter: not resolved, has time remaining
        active_markets = [
            m for m in markets 
            if not m.resolved and m.time_remaining() > 0
        ]
        
        if not active_markets:
            logger.warning("⚠️ No active markets found")
            return None
        
        # Get the one ending soonest
        current = min(active_markets, key=lambda m: m.time_remaining())
        
        logger.info(f"✅ Current market: {current.title} (ends in {current.time_remaining()}s)")
        
        return current
    
    def get_orderbook(self, market_id: int) -> dict:
        """
        Get orderbook for a market
        
        Args:
            market_id: Market ID
            
        Returns:
            dict: Orderbook with bids and asks
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            url = f"{self.base_url}/markets/{market_id}/orderbook"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            orderbook = response.json()
            
            logger.info(f"✅ Got orderbook for market {market_id}")
            
            return orderbook
            
        except Exception as e:
            logger.error(f"❌ Failed to get orderbook: {e}")
            return {'bids': [], 'asks': []}


# Singleton
market_service = MarketService()
