"""
오봇 (O-Bot) - Opinion 전용 Flask Application
경봇(Predict) 코드는 제거됨. 이 레포는 Opinion 다중 로그인·수동/자동 거래만 포함합니다.
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import logging
import re
from config import Config
from core.btc_price import btc_price_service

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
    """Opinion 다중 로그인 대시보드"""
    return render_template('opinion.html')


# ---------- Opinion API (다중 로그인) ----------
from core.opinion_config import has_proxy, OPINION_API_KEY, OPINION_PROXY
from core.opinion_account import opinion_account_manager
from core.opinion_client import (
    get_markets,
    get_market,
    get_latest_price,
    get_orderbook,
    get_price_history,
    get_quote_tokens,
    get_positions,
    get_trades,
)
from core.opinion_btc_topic import get_latest_bitcoin_up_down_market
from core.opinion_manual_trade import get_1h_market_for_trade, execute_manual_trade
from core.opinion_errors import get_auto_error_message, interpret_opinion_api_response
from core.opinion_auto_trader import opinion_auto_trader


def _opinion_auth():
    """Opinion 읽기용 API키·프록시. 없으면 (None, None)."""
    if not OPINION_API_KEY or not has_proxy():
        return None, None
    return OPINION_API_KEY, OPINION_PROXY


@app.route('/api/opinion/proxy-status')
def opinion_proxy_status():
    """프록시 설정 여부. 없으면 UI에서 '프록시를 추가해 주세요' 알림용."""
    return jsonify({'has_proxy': has_proxy()})


@app.route('/api/opinion/accounts')
def opinion_accounts():
    """등록된 Opinion 계정 목록."""
    try:
        accounts = [a.to_dict() for a in opinion_account_manager.get_all()]
        return jsonify({'success': True, 'accounts': accounts, 'has_proxy': has_proxy()})
    except Exception as e:
        logger.exception('opinion accounts: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/login', methods=['POST'])
def opinion_login():
    """
    OKX Wallet PK로 로그인. 리턴값(positions, trades 등) 전부 반환.
    Body: { "private_key": "0x..." }
    """
    try:
        data = request.get_json() or {}
        pk = (data.get('private_key') or '').strip()
        if not pk:
            return jsonify({'success': False, 'error': 'private_key를 입력해 주세요.'}), 400
        name = (data.get('name') or '').strip() or None
        result = opinion_account_manager.login_with_pk(pk, name=name)
        if result.get('success'):
            return jsonify(result)
        code = result.get('code')
        if code == 'NO_PROXY':
            return jsonify(result), 400
        return jsonify(result), 400
    except Exception as e:
        logger.exception('opinion login: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------- Opinion OpenAPI 프록시 ----------

@app.route('/api/opinion/btc-up-down')
def opinion_btc_up_down():
    """Bitcoin Up or Down 시리즈 중 최신 시장 전체 리턴값. 1시간 캐시."""
    try:
        api_key, proxy = _opinion_auth()
        if not api_key:
            return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
        topic_id, market = get_latest_bitcoin_up_down_market()
        if not topic_id or not market:
            return jsonify({'success': False, 'error': 'Bitcoin Up or Down 시장을 찾을 수 없습니다.'}), 404
        return jsonify({'success': True, 'topicId': topic_id, 'result': market})
    except Exception as e:
        logger.exception('btc-up-down error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


def _opinion_cutoff_seconds(market: dict) -> int | None:
    """시장 종료 시각(Unix 초). cutoffAt 또는 collection.current.endTime."""
    cur = market.get("collection") and market.get("collection").get("current")
    if cur and cur.get("endTime") is not None:
        try:
            t = int(float(cur["endTime"]))
            return t if t < 1e12 else t // 1000
        except (TypeError, ValueError):
            pass
    cutoff = market.get("cutoffAt") or 0
    try:
        t = int(float(cutoff))
        return t if t < 1e12 else t // 1000
    except (TypeError, ValueError):
        pass
    return None


def _format_close_kst(cutoff_sec: int) -> str:
    """종료 시각을 KST(서울) 문자열로. 예: Feb 19, 2026 21:00 KST Close."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dt = datetime.fromtimestamp(cutoff_sec, tz=ZoneInfo("Asia/Seoul"))
    return dt.strftime("%b %d, %Y %H:%M KST Close")


def _opinion_market_start_timestamp(market: dict) -> int | None:
    """
    Opinion 시장에서 구간 시작 시각(Unix 초) 추출.
    collection.current.startTime 우선, 없으면 cutoffAt - 3600 (1시간 구간 가정).
    """
    cur = market.get("collection") and market.get("collection").get("current")
    if cur and cur.get("startTime") is not None:
        try:
            t = int(float(cur["startTime"]))
            return t // 1000 if t > 1e12 else t
        except (TypeError, ValueError):
            pass
    cutoff = market.get("cutoffAt") or 0
    try:
        t = int(float(cutoff))
        if t > 1e12:
            t = t // 1000
        if t > 0:
            return t - 3600
    except (TypeError, ValueError):
        pass
    return None


@app.route('/api/opinion/btc-price-gap')
def opinion_btc_price_gap():
    """
    주청(1시간 구간) 기준 Bitcoin 시세 + Gap.
    - Opinion: 해당 토픽의 **시작 타임스탬프**만 사용 (리턴값의 startPrice는 사용 안 함).
    - 시작 시 BTC 가격: Pyth Benchmarks API로 해당 시각 조회 (같은 구간은 캐시로 매번 호출 안 함).
    - 현재 시세: Pyth 실시간.
    """
    try:
        topic_id, market = get_latest_bitcoin_up_down_market()
        if not topic_id or not market:
            return jsonify({'success': False, 'error': '1시간 마켓 없음'}), 404
        start_ts = _opinion_market_start_timestamp(market)
        if start_ts is None:
            return jsonify({
                'success': False,
                'error': '이 시장의 구간 시작 시각을 알 수 없습니다. (cutoffAt 또는 collection.current.startTime 필요)',
                'topicId': topic_id,
            }), 404
        start_price = btc_price_service.get_price_at_timestamp(start_ts)
        if start_price is None:
            return jsonify({
                'success': False,
                'error': 'Pyth에서 해당 시각의 BTC 가격을 가져오지 못했습니다. (Benchmarks API)',
                'topicId': topic_id,
                'startTimestamp': start_ts,
            }), 404
        current_price = btc_price_service.get_current_price()
        gap = round(current_price - start_price, 2)
        cur = market.get("collection") and market.get("collection").get("current")
        period_label = (cur.get("period") or "").strip() or None if cur else None
        base_title = market.get('marketTitle') or 'BTC Up or Down - Hourly'
        # API 제목에 "(... UTC ...)" 괄호가 있으면 제거 후 KST로 대체
        base_clean = re.sub(r"\s*\([^)]*UTC[^)]*\)\s*$", "", base_title).strip() or base_title
        close_kst = None
        cutoff_sec = _opinion_cutoff_seconds(market)
        if cutoff_sec is not None:
            close_kst = _format_close_kst(cutoff_sec)
        market_title_display = f"{base_clean} ({close_kst})" if close_kst else base_clean
        return jsonify({
            'success': True,
            'topicId': topic_id,
            'marketTitle': base_title,
            'marketTitleDisplay': market_title_display,
            'periodLabel': period_label,
            'startPrice': start_price,
            'currentPrice': current_price,
            'gap': gap,
            'startTimestamp': start_ts,
        })
    except Exception as e:
        logger.exception('btc-price-gap error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/manual-trade/status')
def opinion_manual_trade_status():
    """1시간 마켓 수동 거래 상태 (전략 미리보기, 계정 추천). Query: topic_id(선택), shares(기본 10)."""
    try:
        topic_id = request.args.get('topic_id', type=int)
        shares = request.args.get('shares', 10, type=int)
        shares = max(1, min(shares, 1000))
        status = get_1h_market_for_trade(topic_id=topic_id, skip_time_check=True, skip_gap_check=True, shares=shares)
        if not status.get('success'):
            return jsonify({'success': False, 'error': status.get('error', '상태 조회 실패')}), 400
        return jsonify({'success': True, **status})
    except Exception as e:
        logger.exception('opinion manual trade status: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/manual-trade/execute', methods=['POST'])
def opinion_manual_trade_execute():
    """1시간 마켓 수동 거래 실행. Body: topic_id(선택), account_id, shares, direction(UP|DOWN)."""
    try:
        data = request.get_json() or {}
        topic_id = data.get('topic_id')
        account_id = data.get('account_id')
        shares = data.get('shares', 10)
        direction = (data.get('direction') or '').strip().upper()
        if topic_id is not None:
            try:
                topic_id = int(topic_id)
            except (TypeError, ValueError):
                topic_id = None
        try:
            shares = int(shares)
        except (TypeError, ValueError):
            shares = 10
        shares = max(1, min(shares, 1000))
        # direction 없으면 서버 추천(trade_direction) 사용. UP/DOWN이 아니면 execute_manual_trade 내부에서 status 기준으로 채움
        if direction and direction not in ('UP', 'DOWN'):
            return jsonify({'success': False, 'error': 'direction은 UP 또는 DOWN이어야 합니다.'}), 400
        result = execute_manual_trade(
            topic_id=topic_id,
            shares=shares,
            direction=direction or None,
            maker_account_id=int(account_id) if account_id is not None else None,
        )
        if result.get('success'):
            return jsonify(result)
        return jsonify(result), 400
    except Exception as e:
        logger.exception('opinion manual trade execute: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/auto/start', methods=['POST'])
def opinion_auto_start():
    """자동 거래 시작. Body: account_id(선택)."""
    try:
        data = request.get_json() or {}
        account_id = data.get('account_id')
        result = opinion_auto_trader.start(account_id=account_id)
        if result.get('success'):
            return jsonify(result)
        return jsonify(result), 400
    except Exception as e:
        logger.exception('opinion auto start: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/auto/stop', methods=['POST'])
def opinion_auto_stop():
    """자동 거래 중지."""
    try:
        result = opinion_auto_trader.stop()
        return jsonify(result)
    except Exception as e:
        logger.exception('opinion auto stop: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/auto/status')
def opinion_auto_status():
    """자동 거래 상태 (running, account_id, last_error 등)."""
    try:
        status = opinion_auto_trader.get_status()
        return jsonify({'success': True, **status})
    except Exception as e:
        logger.exception('opinion auto status: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/auto/error-message')
def opinion_auto_error_message():
    """마지막 자동 거래 오류 메시지 (UI용)."""
    try:
        msg = get_auto_error_message()
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        logger.exception('opinion auto error message: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/auto/stats')
def opinion_auto_stats():
    """자동 거래 통계 (성공/실패 횟수 등)."""
    try:
        stats = opinion_auto_trader.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.exception('opinion auto stats: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


def _opinion_overall_volume(range_key: str):
    """총 거래량: 모든 Opinion 계정의 trades를 기간별로 집계. range_key: 6h, 1d, 7d, 30d."""
    import time
    from collections import defaultdict
    now = int(time.time())
    ranges = {'6h': 6 * 3600, '1d': 24 * 3600, '7d': 7 * 86400, '30d': 30 * 86400}
    delta = ranges.get(range_key.lower(), 24 * 3600)
    since = now - delta
    api_key, proxy = _opinion_auth()
    if not api_key:
        return None
    accounts = opinion_account_manager.get_all()
    all_ts_vol = []  # (timestamp_sec, volume)
    for acc in accounts:
        try:
            res = get_trades(acc.eoa, api_key, proxy, page=1, limit=100)
            data = res.get('data') or res.get('result') or {}
            if isinstance(data, dict) and 'data' in data:
                data = data.get('data')
            items = data if isinstance(data, list) else []
            for t in items:
                ts = t.get('createdAt') or t.get('timestamp') or t.get('time') or 0
                if isinstance(ts, str) and ts.isdigit():
                    ts = int(ts)
                elif isinstance(ts, (int, float)):
                    ts = int(ts)
                    if ts > 1e12:
                        ts = ts // 1000
                else:
                    continue
                if ts < since:
                    continue
                vol = float(t.get('size') or t.get('amount') or t.get('value') or t.get('volume') or 1)
                all_ts_vol.append((ts, vol))
        except Exception as e:
            logger.debug('overall volume account %s: %s', acc.id, e)
    # 버킷: 6h=1h당, 1d=1h당, 7d=1일당, 30d=1일당
    bucket_sec = 3600 if range_key in ('6h', '1d') else 86400
    buckets = defaultdict(float)
    for ts, vol in all_ts_vol:
        b = (ts // bucket_sec) * bucket_sec
        buckets[b] += vol
    keys = sorted(buckets.keys())
    labels = []
    data = []
    for k in keys:
        from datetime import datetime
        dt = datetime.utcfromtimestamp(k)
        labels.append(dt.strftime('%m/%d %H:%M' if bucket_sec == 3600 else '%m/%d'))
        data.append(round(buckets[k], 2))
    return {'labels': labels, 'data': data}


def _opinion_overall_usdt():
    """모든 Opinion 계정 EOA의 USDT 잔액 합계 + 계정별."""
    try:
        from core.okx_balance import get_usdt_balance_for_address
    except ImportError:
        return None
    accounts = opinion_account_manager.get_all()
    by_account = []
    total = 0.0
    for acc in accounts:
        bal = None
        try:
            proxies = {'http': acc.proxy, 'https': acc.proxy} if getattr(acc, 'proxy', None) else None
            bal = get_usdt_balance_for_address(acc.eoa, proxies=proxies)
        except Exception:
            pass
        val = round(float(bal), 2) if bal is not None else None
        by_account.append({'id': acc.id, 'eoa_short': (acc.eoa or '')[:10] + '...', 'balance': val})
        if val is not None:
            total += val
    return {'total': round(total, 2), 'by_account': by_account, 'labels': ['현재'], 'data': [round(total, 2)]}


@app.route('/api/opinion/overall')
def opinion_overall():
    """Overall 카드: 총 거래량 또는 USDT 총합. Query: metric=volume|usdt, range=6h|1d|7d|30d."""
    try:
        metric = (request.args.get('metric') or 'volume').strip().lower()
        range_key = (request.args.get('range') or '1d').strip().lower()
        if metric == 'usdt':
            out = _opinion_overall_usdt()
            if out is None:
                return jsonify({'success': False, 'error': 'USDT 잔액 조회 모듈을 사용할 수 없습니다.'}), 500
            return jsonify({'success': True, 'metric': 'usdt', 'range': range_key, **out})
        if metric == 'volume':
            out = _opinion_overall_volume(range_key)
            if out is None:
                return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
            return jsonify({'success': True, 'metric': 'volume', 'range': range_key, **out})
        return jsonify({'success': False, 'error': 'metric은 volume 또는 usdt여야 합니다.'}), 400
    except Exception as e:
        logger.exception('opinion overall: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opinion/markets')
def opinion_markets():
    """시장 목록. Query: status, sortBy, page, limit (기본 activated, 20개)."""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    status = request.args.get('status', 'activated')
    sort_by = request.args.get('sortBy', type=int)
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(max(1, limit), 20)
    res = get_markets(api_key, proxy, status=status, sort_by=sort_by, page=page, limit=limit)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/opinion/market/<int:market_id>')
def opinion_market_detail(market_id):
    """시장 상세. GET /market/{marketId}"""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    res = get_market(market_id, api_key, proxy)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/opinion/token/latest-price')
def opinion_token_latest_price():
    """토큰 최신 가격. Query: token_id"""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    token_id = request.args.get('token_id', '').strip()
    if not token_id:
        return jsonify({'success': False, 'error': 'token_id 필요'}), 400
    res = get_latest_price(token_id, api_key, proxy)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/opinion/token/orderbook')
def opinion_token_orderbook():
    """토큰 호가창. Query: token_id"""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    token_id = request.args.get('token_id', '').strip()
    if not token_id:
        return jsonify({'success': False, 'error': 'token_id 필요'}), 400
    res = get_orderbook(token_id, api_key, proxy)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/opinion/token/price-history')
def opinion_token_price_history():
    """가격 히스토리. Query: token_id, interval (기본 1d)"""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    token_id = request.args.get('token_id', '').strip()
    if not token_id:
        return jsonify({'success': False, 'error': 'token_id 필요'}), 400
    interval = request.args.get('interval', '1d')
    res = get_price_history(token_id, api_key, proxy, interval=interval)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/opinion/quote-tokens')
def opinion_quote_tokens():
    """거래 통화 목록. GET /quoteToken"""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    res = get_quote_tokens(api_key, proxy)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/opinion/positions/<path:wallet_address>')
def opinion_positions(wallet_address):
    """특정 지갑 포지션. Query: page, limit"""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(max(1, limit), 20)
    res = get_positions(wallet_address.strip(), api_key, proxy, page=page, limit=limit)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/opinion/trades/<path:wallet_address>')
def opinion_trades(wallet_address):
    """특정 지갑 거래 내역. Query: page, limit"""
    api_key, proxy = _opinion_auth()
    if not api_key:
        return jsonify({'success': False, 'error': 'API 키 또는 프록시를 설정해 주세요.'}), 400
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(max(1, limit), 20)
    res = get_trades(wallet_address.strip(), api_key, proxy, page=page, limit=limit)
    if not res.get('ok'):
        return jsonify({'success': False, 'error': res.get('data') or res.get('error', 'API 오류')}), 502
    return jsonify({'success': True, 'result': res.get('data')})


@app.route('/api/btc/price')
def get_btc_price():
    """Get current BTC price (Pyth 실시간)."""
    try:
        price = btc_price_service.get_current_price()
        return jsonify({'success': True, 'price': price})
    except Exception as e:
        logger.error("BTC price error: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    import os
    # 오봇 전용 레포: Predict 설정 검증·Telegram 미사용
    logger.info("ℹ️ 오봇(O-Bot) Opinion 전용 모드")

    # Bitcoin 실시간 시세: Pyth Hermes SSE 스트림 백그라운드 시작
    try:
        btc_price_service.start_stream()
    except Exception as e:
        logger.warning("⚠️ BTC 시세 스트림 미시작 (REST fallback 사용): %s", e)

    port = int(os.getenv('PORT', 5001))
    app.run(
        debug=Config.DEBUG,
        host='0.0.0.0',
        port=port,
        threaded=True
    )
