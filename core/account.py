"""
Account Management Module - Handle multiple OKX Wallet accounts with proxies
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from eth_account import Account as EthAccount
from config import Config

logger = logging.getLogger(__name__)
ACCOUNTS_JSON = Path(__file__).resolve().parent.parent / 'data' / 'accounts.json'


class Account:
    """Single account representation"""
    
    def __init__(self, account_id: int, private_key: str, proxy: str):
        self.id = account_id
        self.private_key = private_key
        self.proxy = proxy
        self.address = None
        self.username = None
        self.balance = 0.0
        self.unclaimed = 0.0
        self.is_logged_in = False
        
        # Generate address from private key
        try:
            eth_account = EthAccount.from_key(private_key)
            self.address = eth_account.address
            self.is_logged_in = True  # PK로 정상 로드됨 = Active
            logger.info(f"✅ Account {account_id} initialized: {self.address}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize account {account_id}: {e}")
            raise
    
    def get_proxy_dict(self):
        """
        Convert proxy string to dictionary for requests
        
        Returns:
            dict: Proxy configuration for requests library
        """
        # Format: IP:PORT:USER:PASS
        parts = self.proxy.split(':')
        if len(parts) != 4:
            raise ValueError(f"Invalid proxy format: {self.proxy}")
        
        ip, port, user, password = parts
        proxy_url = f"http://{user}:{password}@{ip}:{port}"
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def update_balance(self, balance: float, unclaimed: float = 0.0):
        """Update account balance"""
        self.balance = balance
        self.unclaimed = unclaimed
        logger.info(f"💰 Account {self.id} Balance: ${balance:.2f} | Unclaimed: ${unclaimed:.2f}")
    
    def to_dict(self):
        """Convert account to dictionary for API response"""
        proxy_ip = self.proxy.split(':')[0] if self.proxy else 'N/A'
        nickname = self.username or (self.address[:6] + '...' + self.address[-4:] if self.address else 'N/A')
        return {
            'id': self.id,
            'address': self.address,
            'username': self.username,
            'nickname': nickname,
            'balance': self.balance,
            'unclaimed': self.unclaimed,
            'proxy_ip': proxy_ip,
            'is_logged_in': self.is_logged_in
        }


class AccountManager:
    """Manage multiple accounts"""
    
    def __init__(self):
        self.accounts: List[Account] = []
        self._load_accounts()
    
    def _load_accounts(self):
        """Load from data/accounts.json or Config (env)"""
        if ACCOUNTS_JSON.exists():
            try:
                with open(ACCOUNTS_JSON) as f:
                    data = json.load(f)
                    for item in data.get('accounts', []):
                        self._load_one(item)
                    if self.accounts:
                        logger.info(f"✅ Loaded {len(self.accounts)} accounts from JSON")
                        return
            except Exception as e:
                logger.warning(f"⚠️ Failed to load {ACCOUNTS_JSON}: {e}")
        for account_config in Config.ACCOUNTS:
            try:
                pk = account_config.get('private_key')
                proxy = account_config.get('proxy')
                if not pk or not proxy:
                    logger.warning(
                        f"⚠️ Skipping account {account_config.get('id')}: "
                        "missing private_key or proxy in config"
                    )
                    continue
                account = Account(
                    account_id=account_config['id'],
                    private_key=pk,
                    proxy=proxy
                )
                self.accounts.append(account)
            except Exception as e:
                logger.error(f"❌ Failed to load account {account_config.get('id', '?')}: {e}")
        
        logger.info(f"✅ Loaded {len(self.accounts)} accounts")
    
    def _load_one(self, item: dict):
        try:
            pk = (item.get('private_key') or '').strip()
            proxy = (item.get('proxy') or '').strip()
            if not pk or not proxy:
                return
            acc = Account(account_id=int(item.get('id', 0)), private_key=pk, proxy=proxy)
            acc.username = item.get('username') or item.get('nickname')
            self.accounts.append(acc)
        except Exception as e:
            logger.error(f"❌ Failed to load account {item.get('id')}: {e}")
    
    def upsert_account(self, slot: int, private_key: str, proxy: Optional[str] = None):
        """Add or update account. Proxy는 Config.PROXY_POOL에서 슬롯별 자동 할당."""
        if slot < 1 or slot > 3:
            raise ValueError("Slot must be 1, 2, or 3")
        if not private_key:
            raise ValueError("private_key required")
        if proxy is None or not str(proxy).strip():
            pool = getattr(Config, 'PROXY_POOL', None) or []
            proxy = (pool[slot - 1] if slot <= len(pool) else None) or ''
        proxy = str(proxy).strip()
        if not proxy:
            raise ValueError(f"PROXY_{slot}를 .env에 설정해 주세요.")
        existing = next((a for a in self.accounts if a.id == slot), None)
        if existing:
            self.accounts.remove(existing)
        acc = Account(account_id=slot, private_key=private_key, proxy=proxy)
        self.accounts.append(acc)
        self.accounts.sort(key=lambda a: a.id)
        ACCOUNTS_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(ACCOUNTS_JSON, 'w') as f:
            json.dump({
                'accounts': [{'id': a.id, 'private_key': a.private_key, 'proxy': a.proxy, 'username': getattr(a, 'username', None)} for a in self.accounts]
            }, f, indent=2)
        logger.info(f"✅ Account {slot} saved")
    
    def get_account(self, account_id: int) -> Optional[Account]:
        """Get account by ID"""
        for account in self.accounts:
            if account.id == account_id:
                return account
        return None
    
    def get_all_accounts(self) -> List[Account]:
        """Get all accounts"""
        return self.accounts
    
    def get_account_with_lowest_balance(self) -> Optional[Account]:
        """
        Get account with lowest balance
        This account should be Maker (to win and increase balance)
        """
        if not self.accounts:
            return None
        
        # Filter accounts with balance < MIN_BALANCE
        low_balance_accounts = [a for a in self.accounts if a.balance < Config.MIN_BALANCE]
        
        if low_balance_accounts:
            return min(low_balance_accounts, key=lambda a: a.balance)
        
        # If all accounts have sufficient balance, return None (random assignment)
        return None
    
    def get_total_balance(self) -> float:
        """Get total balance across all accounts"""
        return sum(account.balance for account in self.accounts)
    
    def can_afford_trade(self, shares: int, price_per_share: float) -> bool:
        """
        Check if accounts have enough balance for trade
        
        Args:
            shares: Number of shares
            price_per_share: Average price per share
            
        Returns:
            bool: True if affordable
        """
        required = shares * price_per_share * 2  # Both YES and NO sides
        total = self.get_total_balance()
        
        can_afford = total >= required
        
        if can_afford:
            logger.info(f"✅ Can afford trade: ${total:.2f} >= ${required:.2f}")
        else:
            logger.warning(f"⚠️ Insufficient balance: ${total:.2f} < ${required:.2f}")
        
        return can_afford
    
    def to_list(self):
        """Convert all accounts to list of dicts"""
        return [account.to_dict() for account in self.accounts]


# Singleton instance
account_manager = AccountManager()
