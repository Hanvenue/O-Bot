"""
Telegram Bot Module - Notifications & Kill Switch
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from config import Config

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot for notifications and control"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
        self.app = None
        self.is_running = False
        self.auto_mode_enabled = False
        
    async def start_bot(self):
        """Start the Telegram bot"""
        try:
            self.app = Application.builder().token(self.token).build()
            
            # Register command handlers
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("status", self.cmd_status))
            self.app.add_handler(CommandHandler("stop", self.cmd_stop))
            self.app.add_handler(CommandHandler("resume", self.cmd_resume))
            self.app.add_handler(CommandHandler("help", self.cmd_help))
            
            # Start polling
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            self.is_running = True
            logger.info("✅ Telegram bot started")
            
            # Send startup message
            await self.send_message("🤖 경봇이 시작되었습니다!")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram bot: {e}")
    
    async def stop_bot(self):
        """Stop the Telegram bot"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self.is_running = False
            logger.info("🛑 Telegram bot stopped")
    
    # Command Handlers
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 경봇 (Gyeong Bot)\n\n"
            "사용 가능한 명령어:\n"
            "/status - 현재 상태 확인\n"
            "/stop - 자동 거래 중지 (킬스위치)\n"
            "/resume - 자동 거래 재개\n"
            "/help - 도움말"
        )
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        status = "🟢 실행 중" if self.auto_mode_enabled else "🔴 정지됨"
        await update.message.reply_text(
            f"📊 현재 상태\n\n"
            f"Auto 모드: {status}\n"
            f"Bot 실행: {'✅ Yes' if self.is_running else '❌ No'}"
        )
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command (Kill Switch)"""
        self.auto_mode_enabled = False
        logger.warning("🛑 KILL SWITCH ACTIVATED via Telegram")
        await update.message.reply_text(
            "🛑 킬스위치 활성화!\n\n"
            "모든 자동 거래가 중지되었습니다.\n"
            "/resume 명령으로 재개할 수 있습니다."
        )
    
    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        self.auto_mode_enabled = True
        logger.info("▶️ Auto mode resumed via Telegram")
        await update.message.reply_text(
            "▶️ 자동 거래 재개!\n\n"
            "Auto 모드가 다시 활성화되었습니다."
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(
            "📖 도움말\n\n"
            "🛑 /stop - 긴급 중지\n"
            "  모든 자동 거래를 즉시 중단합니다.\n\n"
            "▶️ /resume - 재개\n"
            "  자동 거래를 다시 시작합니다.\n\n"
            "📊 /status - 상태 확인\n"
            "  현재 봇의 상태를 확인합니다."
        )
    
    # Notification Methods
    
    async def send_message(self, text: str):
        """Send message to Telegram"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
    
    async def notify_trade_executed(self, trade_data: dict):
        """Notify when trade is executed (상세 정보 포함)"""
        price = trade_data.get('price', 0)
        shares = trade_data.get('shares', 0)
        direction = trade_data.get('direction', '?')
        opp = 'DOWN' if direction == 'UP' else 'UP'
        maker_inv = price * shares
        taker_inv = (1 - price) * shares
        total = maker_inv + taker_inv
        fee = taker_inv * 0.002
        message = (
            f"✅ <b>거래 실행 완료</b>\n\n"
            f"<b>Maker {direction}</b>: ${maker_inv:.2f} ({int(price*100)}¢ × {shares})\n"
            f"<b>Taker {opp}</b>: ${taker_inv:.2f}\n\n"
            f"■ 총 투자: ${total:.2f}\n"
            f"예상 수수료: -${fee:.4f}\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send_message(message)
    
    async def notify_trade_failed(self, error: str):
        """Notify when trade fails"""
        message = (
            f"❌ <b>거래 실패</b>\n\n"
            f"에러: {error}\n"
            f"시간: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send_message(message)
    
    async def notify_market_found(self, market_data: dict):
        """Notify when tradeable market is found (동업자 봇 스타일 상세 정보)"""
        base = (
            f"🎯 <b>거래 가능 마켓 발견</b>\n\n"
            f"마켓: {market_data.get('title', 'Unknown')}\n"
            f"방향: {market_data.get('trade_direction', 'N/A')}\n"
            f"가격 갭: ${market_data.get('price_gap', 0):+.2f}\n"
            f"남은 시간: {market_data.get('time_remaining', 0)}초"
        )
        strategy = market_data.get('strategy')
        if strategy:
            s = strategy
            loss_pct = (s['guaranteed_loss'] / s['total_investment'] * 100) if s['total_investment'] else 0
            base += (
                f"\n\n<b>💡 추천 전략</b>\n"
                f"Maker {s['maker_side']} + Taker {s['taker_side']}\n\n"
                f"■ 총 투자금액: ${s['total_investment']:.2f}\n"
                f"확정 손실: -${s['guaranteed_loss']:.4f} (-{loss_pct:.2f}%)\n\n"
                f"Shares: {market_data.get('shares', 10)}"
            )
        await self.send_message(base)
    
    async def notify_balance_low(self, account_id: int, balance: float):
        """Notify when account balance is low"""
        message = (
            f"⚠️ <b>잔액 부족 경고</b>\n\n"
            f"계정 #{account_id}\n"
            f"현재 잔액: ${balance:.2f}\n"
            f"최소 잔액: ${Config.MIN_BALANCE:.2f}"
        )
        await self.send_message(message)


# Singleton instance (will be initialized in app.py)
telegram_bot: Optional[TelegramBot] = None


def init_telegram_bot(token: str, chat_id: str) -> TelegramBot:
    """Initialize Telegram bot"""
    global telegram_bot
    telegram_bot = TelegramBot(token, chat_id)
    return telegram_bot
