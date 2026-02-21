"""
오봇/경봇 공용 설정.
- 오봇(O-Bot) 전용 레포에서는 Config.validate()를 호출하지 않음 (Predict/계정 검증 불필요).
- SECRET_KEY, PYTH, TIME_BEFORE_END, MIN_PRICE_GAP 등 Opinion에서 사용.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트(config.py 있는 폴더)의 .env를 항상 로드 → 어디서 실행해도 O-Bot .env 적용
_root = Path(__file__).resolve().parent
load_dotenv(_root / ".env")

class Config:
    """Central configuration for Gyeong Bot"""
    
    # Predict.fun API
    PREDICT_API_KEY = os.getenv('PREDICT_API_KEY')
    PREDICT_BASE_URL = os.getenv('PREDICT_BASE_URL', 'https://api.predict.fun')
    
    # 프록시 풀: 계정 슬롯별 자동 할당 (.env PROXY_1, PROXY_2, PROXY_3)
    def _p(i):
        v = (os.getenv(f'PROXY_{i}') or '').strip()
        return v or None
    PROXY_POOL = [_p(1), _p(2), _p(3)]
    
    # Accounts (3 accounts with OKX Wallet Private Keys)
    ACCOUNTS = [
        {
            'id': 1,
            'private_key': os.getenv('ACCOUNT_1_PK'),
            'proxy': os.getenv('PROXY_1'),
        },
        {
            'id': 2,
            'private_key': os.getenv('ACCOUNT_2_PK'),
            'proxy': os.getenv('PROXY_2'),
        },
        {
            'id': 3,
            'private_key': os.getenv('ACCOUNT_3_PK'),
            'proxy': os.getenv('PROXY_3'),
        }
    ]
    
    # Pyth Network (BTC Price)
    PYTH_API_URL = os.getenv('PYTH_API_URL', 'https://hermes.pyth.network/api/latest_price_feeds')
    BTC_PRICE_FEED_ID = os.getenv('BTC_PRICE_FEED_ID', '0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43')
    
    # Trading Parameters
    MIN_PRICE_GAP = int(os.getenv('MIN_PRICE_GAP', 200))  # $200
    MIN_BALANCE = float(os.getenv('MIN_BALANCE', 20))  # $20
    TIME_BEFORE_END = int(os.getenv('TIME_BEFORE_END', 300))  # 5 minutes (300 seconds)

    # 실시간 자전거래 (한쪽 주문을 반대쪽이 바로 받도록 지연 최소화)
    POST_MAKER_DELAY_SEC = float(os.getenv('POST_MAKER_DELAY_SEC', '0.2'))  # Maker 직후 대기(초)
    WASH_TRADE_POLL_INTERVAL_SEC = float(os.getenv('WASH_TRADE_POLL_INTERVAL_SEC', '0.4'))  # 체결 폴링 간격
    WASH_TRADE_POLL_TIMEOUT_SEC = float(os.getenv('WASH_TRADE_POLL_TIMEOUT_SEC', '10'))  # 미체결 시 취소까지 대기
    USE_TAKER_MARKET_ORDER = os.getenv('USE_TAKER_MARKET_ORDER', 'true').lower() in ('1', 'true', 'yes')  # Taker MARKET 주문 사용
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    @classmethod
    def validate(cls):
        """Validate essential configuration"""
        errors = []
        
        if not cls.PREDICT_API_KEY:
            errors.append("PREDICT_API_KEY is required")
        
        for i, account in enumerate(cls.ACCOUNTS, 1):
            if not account['private_key']:
                errors.append(f"ACCOUNT_{i}_PK is required")
            if not account['proxy']:
                errors.append(f"PROXY_{i} is required")
        
        # Telegram is optional
        if cls.TELEGRAM_BOT_TOKEN and not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is required when using Telegram bot")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True
