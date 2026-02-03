"""
Market Module - Handle Predict.fun market data
"""
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, List
from config import Config

logger = logging.getLogger(__name__)


def _sanitize_api_key(key: Optional[str]) -> str:
    """Strip invisible Unicode (e.g. U+2068) from API key to avoid latin-1 encode errors."""
    if not key:
        return ''
    return ''.join(c for c in str(key).strip() if ord(c) < 128 and (c.isalnum() or c in '-'))


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
        Get BTC/USD CRYPTO_UP_DOWN markets (Predict.fun REST API)
        Uses /v1/categories for markets with startsAt/endsAt
        """
        try:
            headers = {
                'x-api-key': _sanitize_api_key(self.api_key)
            }
            base = self.base_url.rstrip('/')
            raw_list = []
            
            # Categories include markets with start/end times
            url = f"{base}/v1/categories"
            params = {
                'marketVariant': 'CRYPTO_UP_DOWN',
                'status': 'OPEN',
                'first': 20
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            categories = data.get('data', []) if data.get('success') else []
            
            for cat in categories:
                for m in cat.get('markets', []):
                    m['_startsAt'] = cat.get('startsAt')
                    m['_endsAt'] = cat.get('endsAt')
                    raw_list.append(m)
            
            # Fallback: /v1/markets if no categories
            if not raw_list:
                mkt_url = f"{base}/v1/markets"
                mkt_resp = requests.get(mkt_url, headers=headers, params={'marketVariant': 'CRYPTO_UP_DOWN', 'status': 'OPEN', 'first': 50}, timeout=10)
                if mkt_resp.ok:
                    mkt_data = mkt_resp.json()
                    raw_list = mkt_data.get('data', []) if mkt_data.get('success') else []
            
            markets = []
            for m in raw_list:
                try:
                    mapped = self._map_api_market_to_internal(m)
                    if mapped:
                        markets.append(Market(mapped))
                except Exception as e:
                    logger.debug(f"Skip market {m.get('id')}: {e}")
            
            logger.info(f"✅ Found {len(markets)} BTC CRYPTO_UP_DOWN markets")
            
            return markets
            
        except Exception as e:
            logger.error(f"❌ Failed to get markets: {e}")
            return []
    
    def _map_api_market_to_internal(self, m: dict) -> dict:
        """Map Predict.fun API market format to our Market format"""
        variant = m.get('variantData') or {}
        start_price = variant.get('startPrice') or 0.0
        
        return {
            'id': m.get('id'),
            'title': m.get('title', m.get('question', '')),
            'category': m.get('categorySlug'),
            'start_time': m.get('_startsAt') or m.get('startsAt'),
            'end_time': m.get('_endsAt') or m.get('endsAt'),
            'start_price': start_price,
            'current_price': start_price,
            'yes_price': 0.5,
            'no_price': 0.5,
            'volume': 0.0,
            'resolved': m.get('status') == 'RESOLVED'
        }
    
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
        """Get orderbook for a market (Predict.fun REST API)"""
        try:
            headers = {
                'x-api-key': _sanitize_api_key(self.api_key)
            }
            
            url = f"{self.base_url.rstrip('/')}/v1/markets/{market_id}/orderbook"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            ob = data.get('data', {}) if data.get('success') else {}
            
            logger.info(f"✅ Got orderbook for market {market_id}")
            
            return {
                'bids': ob.get('bids', []),
                'asks': ob.get('asks', [])
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get orderbook: {e}")
            return {'bids': [], 'asks': []}


# Singleton
market_service = MarketService()
