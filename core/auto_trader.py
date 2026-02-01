"""
Auto Trading Engine - Continuous market monitoring and trading
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from config import Config
from core.market import market_service
from core.btc_price import btc_price_service
from core.validator import trade_validator
from core.account import account_manager
from core import trader as trader_module
from core.telegram_bot import telegram_bot

logger = logging.getLogger(__name__)


class AutoTrader:
    """Automatic trading engine"""
    
    def __init__(self):
        self.is_running = False
        self.auto_mode_enabled = False
        self.check_interval = 10  # Check every 10 seconds
        self.last_trade_time = None
        self.trade_cooldown = 60  # 60 seconds cooldown between trades
        self.shares_per_trade = 10  # Default shares
        
        # Statistics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = 0.0
    
    async def start(self, shares: int = 10):
        """
        Start auto trading
        
        Args:
            shares: Number of shares per trade
        """
        if self.is_running:
            logger.warning("⚠️ Auto trader already running")
            return
        
        self.is_running = True
        self.auto_mode_enabled = True
        self.shares_per_trade = shares
        
        logger.info(f"🤖 Auto trader started (shares: {shares})")
        
        if telegram_bot:
            await telegram_bot.send_message(
                f"🤖 <b>Auto 모드 시작</b>\n\n"
                f"Shares: {shares}\n"
                f"체크 간격: {self.check_interval}초"
            )
        
        # Start monitoring loop
        await self._monitoring_loop()
    
    def stop(self):
        """Stop auto trading"""
        self.is_running = False
        self.auto_mode_enabled = False
        logger.info("🛑 Auto trader stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                # Check if auto mode still enabled (can be disabled by Telegram)
                if telegram_bot and not telegram_bot.auto_mode_enabled:
                    self.auto_mode_enabled = False
                    logger.warning("🛑 Auto mode disabled via Telegram")
                    break
                
                if not self.auto_mode_enabled:
                    await asyncio.sleep(self.check_interval)
                    continue
                
                # Check cooldown
                if not self._can_trade():
                    await asyncio.sleep(self.check_interval)
                    continue
                
                # Get current market
                market = market_service.get_current_market()
                
                if not market:
                    logger.debug("⏳ No active market found")
                    await asyncio.sleep(self.check_interval)
                    continue
                
                # Validate trade conditions
                is_valid, direction, reason = trade_validator.validate_market({
                    'end_time': market.end_time,
                    'start_price': market.start_price
                })
                
                if not is_valid:
                    logger.debug(f"⏳ Trade conditions not met: {reason}")
                    await asyncio.sleep(self.check_interval)
                    continue
                
                # Trade conditions met! Get orderbook for strategy preview
                orderbook = market_service.get_orderbook(market.id)
                price_valid, maker_price = trade_validator.validate_orderbook(orderbook, direction)
                strategy_info = None
                if price_valid and maker_price:
                    taker_price = 1.0 - maker_price
                    maker_inv = maker_price * self.shares_per_trade
                    taker_inv = taker_price * self.shares_per_trade
                    strategy_info = {
                        'maker_side': direction,
                        'taker_side': 'DOWN' if direction == 'UP' else 'UP',
                        'maker_price': maker_price,
                        'total_investment': maker_inv + taker_inv,
                        'guaranteed_loss': taker_inv * 0.002,
                    }
                
                logger.info(f"🎯 Trade conditions met: {direction} - {reason}")
                
                # Notify via Telegram (상세 전략 포함)
                if telegram_bot:
                    await telegram_bot.notify_market_found({
                        'title': market.title,
                        'trade_direction': direction,
                        'price_gap': market.price_gap(),
                        'time_remaining': market.time_remaining(),
                        'shares': self.shares_per_trade,
                        'strategy': strategy_info,
                    })
                
                # Execute trade
                await self._execute_auto_trade(market, direction)
                
                # Update last trade time
                self.last_trade_time = datetime.now()
                
                # Wait longer after a trade
                await asyncio.sleep(self.check_interval * 2)
                
            except Exception as e:
                logger.error(f"❌ Auto trader error: {e}")
                
                if telegram_bot:
                    await telegram_bot.notify_trade_failed(str(e))
                
                await asyncio.sleep(self.check_interval)
        
        logger.info("🛑 Monitoring loop ended")
    
    def _can_trade(self) -> bool:
        """Check if enough time has passed since last trade"""
        if not self.last_trade_time:
            return True
        
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        return elapsed >= self.trade_cooldown
    
    async def _execute_auto_trade(self, market, direction: str):
        """
        Execute automatic trade
        
        Args:
            market: Market object
            direction: Trade direction (UP or DOWN)
        """
        try:
            # Get orderbook
            orderbook = market_service.get_orderbook(market.id)
            
            # Validate orderbook
            price_valid, maker_price = trade_validator.validate_orderbook(orderbook, direction)
            
            if not price_valid:
                logger.error("❌ Orderbook validation failed")
                return
            
            # Check balance
            if not account_manager.can_afford_trade(self.shares_per_trade, maker_price):
                logger.error("❌ Insufficient balance")
                
                if telegram_bot:
                    total_balance = account_manager.get_total_balance()
                    await telegram_bot.send_message(
                        f"⚠️ <b>잔액 부족</b>\n\n"
                        f"현재 잔액: ${total_balance:.2f}\n"
                        f"필요 금액: ${self.shares_per_trade * maker_price * 2:.2f}"
                    )
                return
            
            # Assign accounts (need at least 2 accounts for wash trade)
            maker_account = account_manager.get_account_with_lowest_balance()
            if not maker_account:
                maker_account = account_manager.get_account(1)
            if not maker_account:
                logger.error("❌ No maker account available")
                return
            
            all_accounts = account_manager.get_all_accounts()
            other_accounts = [a for a in all_accounts if a.id != maker_account.id]
            if len(other_accounts) < 1:
                logger.error("❌ Need at least 2 accounts for wash trade")
                return
            taker_account = other_accounts[0]
            
            logger.info(f"🎯 Executing auto trade: {direction} @ ${maker_price:.2f} × {self.shares_per_trade}")
            
            # Execute trade (trader is set by app.py on startup)
            trader = trader_module.trader
            if not trader:
                logger.error("❌ Trader not initialized (app startup order issue)")
                return
            result = trader.execute_wash_trade(
                market_id=market.id,
                maker_account=maker_account,
                taker_account=taker_account,
                direction=direction,
                maker_price=maker_price,
                shares=self.shares_per_trade
            )
            
            if result['success']:
                self.total_trades += 1
                self.successful_trades += 1
                
                logger.info(f"✅ Auto trade executed successfully!")
                
                # Notify via Telegram
                if telegram_bot:
                    await telegram_bot.notify_trade_executed({
                        'direction': direction,
                        'price': maker_price,
                        'shares': self.shares_per_trade
                    })
                
                # Note: Balance update removed - real balance comes from Predict.fun API.
                # Manual update was incorrect (wash trade doesn't simply subtract from maker).
                
            else:
                self.total_trades += 1
                self.failed_trades += 1
                
                logger.error(f"❌ Auto trade failed: {result.get('error')}")
                
                if telegram_bot:
                    await telegram_bot.notify_trade_failed(result.get('error'))
            
        except Exception as e:
            logger.error(f"❌ Auto trade execution error: {e}")
            
            if telegram_bot:
                await telegram_bot.notify_trade_failed(str(e))
    
    def get_statistics(self) -> dict:
        """Get trading statistics"""
        success_rate = (self.successful_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'is_running': self.is_running,
            'auto_mode_enabled': self.auto_mode_enabled,
            'total_trades': self.total_trades,
            'successful_trades': self.successful_trades,
            'failed_trades': self.failed_trades,
            'success_rate': success_rate,
            'total_profit': self.total_profit,
            'shares_per_trade': self.shares_per_trade
        }


# Singleton instance
auto_trader = AutoTrader()
