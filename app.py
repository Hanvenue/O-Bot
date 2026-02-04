"""
경봇 (Gyeong Bot) - Main Flask Application
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import logging
import asyncio
from threading import Thread
from config import Config
from core.account import account_manager
from core.market import market_service
from core.btc_price import btc_price_service
from core.validator import trade_validator
from core.trader import Trader
from core.auto_trader import auto_trader
from core.telegram_bot import init_telegram_bot, telegram_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24시간

# Initialize trader (will use actual Predict client later)
trader = Trader(predict_client=None)  # TODO: Initialize with Predict SDK

# Share trader instance with auto_trader (auto_trader imports from core.trader)
import core.trader as trader_module
trader_module.trader = trader

# 접속 암호 (하드코딩)
ACCESS_PASSWORD = 'ansckdrhk13!'


@app.before_request
def require_login():
    """로그인되지 않은 사용자는 접속 페이지로 리다이렉트"""
    if request.endpoint in (None, 'static'):
        return
    if request.endpoint == 'login' or request.path == url_for('login'):
        return
    if request.endpoint == 'check_password' or request.path == url_for('check_password'):
        return
    if not session.get('authenticated'):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Unauthorized', 'redirect': url_for('login')}), 401
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """접속 페이지 - 암호 입력"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ACCESS_PASSWORD:
            session['authenticated'] = True
            session.permanent = True
            return redirect(url_for('index'))
        return render_template('login.html', error='암호가 올바르지 않습니다.')
    return render_template('login.html')


@app.route('/login/check', methods=['POST'])
def check_password():
    """API용 암호 확인 (JSON)"""
    data = request.get_json() or {}
    password = data.get('password', '')
    if password == ACCESS_PASSWORD:
        session['authenticated'] = True
        session.permanent = True
        return jsonify({'success': True, 'redirect': url_for('index')})
    return jsonify({'success': False, 'error': 'Invalid password'}), 401


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get system status"""
    try:
        accounts = account_manager.to_list()
        total_balance = account_manager.get_total_balance()
        
        return jsonify({
            'success': True,
            'accounts': accounts,
            'total_accounts': len(accounts),
            'total_balance': total_balance
        })
    except Exception as e:
        logger.error(f"❌ Status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


MAX_ACCOUNTS = 3


@app.route('/api/accounts', methods=['GET', 'POST'])
def manage_accounts():
    """계정 추가/수정. POST: { slot: 1|2|3, private_key } - 프록시는 config에서 자동 할당"""
    if request.method == 'POST':
        data = request.get_json() or {}
        slot = data.get('slot', 1)
        pk = (data.get('private_key') or '').strip()
        try:
            slot = int(slot)
        except (TypeError, ValueError):
            slot = 1
        if slot < 1 or slot > MAX_ACCOUNTS:
            return jsonify({'success': False, 'error': '계정은 최대 3개까지 가능합니다.'}), 400
        current = account_manager.to_list()
        if len(current) >= MAX_ACCOUNTS and not any(a.get('id') == slot for a in current):
            return jsonify({'success': False, 'error': '계정은 최대 3개까지 가능합니다.'}), 400
        try:
            account_manager.upsert_account(slot, pk)
            return jsonify({'success': True})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f"❌ Account save error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': True, 'accounts': account_manager.to_list(), 'max_accounts': MAX_ACCOUNTS})


@app.route('/api/market/current')
def get_current_market():
    """Get current active market with optional strategy preview"""
    try:
        market = market_service.get_current_market()
        
        if not market:
            return jsonify({
                'success': False,
                'error': 'No active market'
            })
        
        # Get BTC price and gap
        current_btc = btc_price_service.get_current_price()
        gap = current_btc - market.start_price
        
        # Check if trade ready
        is_valid, direction, reason = trade_validator.validate_market({
            'end_time': market.end_time,
            'start_price': market.start_price
        })
        
        market_data = market.to_dict()
        market_data['current_btc_price'] = current_btc
        market_data['price_gap'] = gap
        market_data['trade_ready'] = is_valid
        market_data['trade_direction'] = direction
        market_data['trade_reason'] = reason
        
        # YES/NO 실시간 가격 (호가창에서 추출)
        yes_p, no_p = market_service.get_yes_no_prices_from_orderbook(market.id)
        if yes_p is not None:
            market_data['yes_price'] = yes_p
        if no_p is not None:
            market_data['no_price'] = no_p
        
        # Strategy preview when trade ready (shares from query param)
        shares = request.args.get('shares', type=int, default=10)
        shares = max(1, shares) if shares else 10
        if is_valid and direction:
            orderbook = market_service.get_orderbook(market.id)
            price_valid, maker_price = trade_validator.validate_orderbook(orderbook, direction)
            if price_valid and maker_price:
                taker_price = 1.0 - maker_price
                maker_investment = maker_price * shares
                taker_investment = taker_price * shares
                total_investment = maker_investment + taker_investment
                taker_fee = taker_investment * 0.002  # 0.2% taker fee
                maker_profit_if_win = (1 - maker_price) * shares
                taker_profit_if_win = (1 - taker_price) * shares
                # 계정 배정 (실행 시와 동일한 로직)
                maker_account = account_manager.get_account_with_lowest_balance()
                if not maker_account:
                    maker_account = account_manager.get_account(1)
                other_accounts = [a for a in account_manager.get_all_accounts() if maker_account and a.id != maker_account.id]
                taker_account = other_accounts[0] if other_accounts else None
                
                maker_data = {
                    'side': direction,
                    'shares': shares,
                    'price': round(maker_price, 2),
                    'price_display': f'{int(maker_price*100)}¢',
                    'investment': round(maker_investment, 2),
                    'profit_if_win': round(maker_profit_if_win, 2),
                    'fee': 0,
                    'account_id': maker_account.id if maker_account else None,
                }
                taker_data = {
                    'side': 'DOWN' if direction == 'UP' else 'UP',
                    'shares': shares,
                    'price': round(taker_price, 2),
                    'price_display': f'{int(taker_price*100)}¢',
                    'investment': round(taker_investment, 2),
                    'profit_if_win': round(taker_profit_if_win, 2),
                    'fee': round(taker_fee, 4),
                    'account_id': taker_account.id if taker_account else None,
                }
                market_data['strategy_preview'] = {
                    'status': 'arbitrage_ready',
                    'status_message': '차익거래 가능 - Maker-Taker 전략',
                    'recommended_strategy': f'Maker {direction} + Taker {"DOWN" if direction == "UP" else "UP"}',
                    'maker': maker_data,
                    'taker': taker_data,
                    'total_investment': round(total_investment, 2),
                    'guaranteed_loss': round(taker_fee, 4),
                    'loss_rate_pct': round(taker_fee / total_investment * 100, 2) if total_investment else 0,
                    'outcome_summary': {
                        'total_received': round(total_investment, 2),
                        'net_loss': round(-taker_fee, 2),
                        'message': '어느 결과가 나와도 총 투자금액 회수, 수수료만 손실'
                    }
                }
            else:
                market_data['strategy_preview'] = {
                    'status': 'no_orderbook',
                    'status_message': '호가창 데이터 없음 - 거래 대기',
                    'recommended_strategy': None,
                }
        else:
            market_data['strategy_preview'] = {
                'status': 'waiting',
                'status_message': f'거래 조건 대기 중 - {reason}',
                'recommended_strategy': None,
            }
        
        return jsonify({
            'success': True,
            'market': market_data
        })
        
    except Exception as e:
        logger.error(f"❌ Market error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/market/<int:market_id>/orderbook')
def get_market_orderbook(market_id):
    """Get orderbook for market"""
    try:
        orderbook = market_service.get_orderbook(market_id)
        
        return jsonify({
            'success': True,
            'orderbook': orderbook
        })
        
    except Exception as e:
        logger.error(f"❌ Orderbook error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trade/execute', methods=['POST'])
def execute_trade():
    """
    Execute wash trade
    
    Body:
        {
            "market_id": 123,
            "shares": 10,
            "direction": "UP" (optional, auto-detect if not provided)
        }
    """
    try:
        data = request.get_json() or {}
        
        market_id = data.get('market_id')
        shares = data.get('shares')
        direction = data.get('direction')  # Can be None (auto-detect)
        
        # Ensure correct types (JSON may send strings)
        try:
            market_id = int(market_id) if market_id is not None else None
        except (TypeError, ValueError):
            market_id = None
        try:
            shares = int(shares) if shares is not None else None
        except (TypeError, ValueError):
            shares = None
        
        if not market_id or shares is None or shares < 1:
            return jsonify({
                'success': False,
                'error': 'Missing or invalid market_id or shares (must be >= 1)'
            }), 400
        
        # Get market
        market = market_service.get_current_market()
        if not market or market.id != market_id:
            return jsonify({
                'success': False,
                'error': 'Invalid market'
            }), 400
        
        # Validate conditions (skip 5-min check for manual trade)
        is_valid, auto_direction, reason = trade_validator.validate_market({
            'end_time': market.end_time,
            'start_price': market.start_price
        }, skip_time_check=True)
        
        if not is_valid:
            return jsonify({
                'success': False,
                'error': f'Trade conditions not met: {reason}'
            }), 400
        
        # Use auto-detected direction if not provided
        final_direction = direction or auto_direction
        
        # Get orderbook and optimal price
        orderbook = market_service.get_orderbook(market_id)
        price_valid, maker_price = trade_validator.validate_orderbook(orderbook, final_direction)
        
        if not price_valid:
            return jsonify({
                'success': False,
                'error': 'Orderbook validation failed'
            }), 400
        
        # Check balance
        if not account_manager.can_afford_trade(shares, maker_price):
            return jsonify({
                'success': False,
                'error': 'Insufficient balance'
            }), 400
        
        # Assign accounts (need at least 2 for wash trade)
        maker_account = account_manager.get_account_with_lowest_balance()
        if not maker_account:
            maker_account = account_manager.get_account(1)
        if not maker_account:
            return jsonify({
                'success': False,
                'error': 'No accounts available'
            }), 400
        
        other_accounts = [a for a in account_manager.get_all_accounts() if a.id != maker_account.id]
        if len(other_accounts) < 1:
            return jsonify({
                'success': False,
                'error': 'Need at least 2 accounts for wash trade'
            }), 400
        taker_account = other_accounts[0]
        
        # Execute trade
        result = trader.execute_wash_trade(
            market_id=market_id,
            maker_account=maker_account,
            taker_account=taker_account,
            direction=final_direction,
            maker_price=maker_price,
            shares=shares
        )
        
        if result['success']:
            logger.info(f"✅ Trade executed successfully")
        else:
            logger.error(f"❌ Trade failed: {result.get('error')}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Trade execution error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/btc/price')
def get_btc_price():
    """Get current BTC price"""
    try:
        price = btc_price_service.get_current_price()
        
        return jsonify({
            'success': True,
            'price': price
        })
        
    except Exception as e:
        logger.error(f"❌ BTC price error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auto/start', methods=['POST'])
def start_auto_mode():
    """
    Start auto trading mode
    
    Body:
        {
            "shares": 10
        }
    """
    try:
        data = request.get_json() or {}
        shares = data.get('shares', 10)
        try:
            shares = max(1, int(shares))
        except (TypeError, ValueError):
            shares = 10
        
        if auto_trader.is_running:
            return jsonify({
                'success': False,
                'error': 'Auto mode already running'
            }), 400
        
        # Start auto trader in background
        def run_async_auto_trader():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(auto_trader.start(shares))
        
        thread = Thread(target=run_async_auto_trader, daemon=True)
        thread.start()
        
        logger.info(f"🤖 Auto mode started with {shares} shares")
        
        return jsonify({
            'success': True,
            'message': f'Auto mode started with {shares} shares'
        })
        
    except Exception as e:
        logger.error(f"❌ Auto mode start error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auto/stop', methods=['POST'])
def stop_auto_mode():
    """Stop auto trading mode"""
    try:
        auto_trader.stop()
        
        logger.info("🛑 Auto mode stopped")
        
        return jsonify({
            'success': True,
            'message': 'Auto mode stopped'
        })
        
    except Exception as e:
        logger.error(f"❌ Auto mode stop error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auto/stats')
def get_auto_stats():
    """Get auto trading statistics"""
    try:
        stats = auto_trader.get_statistics()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"❌ Auto stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Validate config
    try:
        Config.validate()
        logger.info("✅ Configuration validated")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        exit(1)
    
    # Initialize Telegram bot (if configured)
    if Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID:
        try:
            init_telegram_bot(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID)
            
            # Start Telegram bot in background
            def run_telegram_bot():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(telegram_bot.start_bot())
            
            telegram_thread = Thread(target=run_telegram_bot, daemon=True)
            telegram_thread.start()
            
            logger.info("✅ Telegram bot initialized")
        except Exception as e:
            logger.warning(f"⚠️ Telegram bot initialization failed: {e}")
    else:
        logger.info("ℹ️ Telegram bot not configured (optional)")
        
    # Run app (포트 5001: macOS AirPlay가 5000 사용 시)
    import os
    port = int(os.getenv('PORT', 5001))
    app.run(
        debug=Config.DEBUG,
        host='0.0.0.0',
        port=port,
        threaded=True
    )
