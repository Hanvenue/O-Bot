"""
Account Management Module - Handle multiple OKX Wallet accounts with proxies
"""
import logging
from typing import Dict, List, Optional
from eth_account import Account as EthAccount
from config import Config

logger = logging.getLogger(__name__)


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
        return {
            'id': self.id,
            'address': self.address,
            'username': self.username,
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
        """Load accounts from config"""
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
