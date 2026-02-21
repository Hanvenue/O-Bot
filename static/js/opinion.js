// Opinion.trade 다중 로그인 UI

/** 직전 거래 성공 여부 카드: 4가지 상태용 이미지 (성공 = static/images/pepe-success.png) */
var LAST_TRADE_PEPE_IMAGES = {
    success: '/static/images/pepe-success.png',
    fail: '/static/images/pepe-fail.png',
    black_swan: '/static/images/pepe-black-swan.png',
    unknown: '/static/images/pepe-unknown.png'
};

/** Shares 입력: noUiSlider + 숫자 입력 동기화 */
function initSharesSlider() {
    var sliderEl = document.getElementById('sharesSlider');
    var inputEl = document.getElementById('manualSharesInput');
    if (!sliderEl || !inputEl || typeof noUiSlider === 'undefined') return;
    noUiSlider.create(sliderEl, {
        start: [parseInt(inputEl.value, 10) || 10],
        connect: [true, false],
        range: { min: 1, max: 1000 },
        step: 1
    });
    sliderEl.noUiSlider.on('update', function (values) {
        var v = values[0];
        if (inputEl.value !== v) inputEl.value = Math.round(parseFloat(v));
        scheduleSharesPriceUpdate();
    });
    function setSliderVal(num) {
        var n = Math.max(1, Math.min(1000, parseInt(num, 10) || 1));
        if (sliderEl.noUiSlider) sliderEl.noUiSlider.set(n);
        inputEl.value = n;
        scheduleSharesPriceUpdate();
    }
    function scheduleSharesPriceUpdate() {
        if (_sharesPriceDebounce) clearTimeout(_sharesPriceDebounce);
        _sharesPriceDebounce = setTimeout(function () { updateSharesPriceDisplay(); _sharesPriceDebounce = null; }, 400);
    }
    inputEl.addEventListener('change', function () { setSliderVal(inputEl.value); });
    inputEl.addEventListener('input', function () {
        var n = parseInt(inputEl.value, 10);
        if (!isNaN(n)) setSliderVal(n);
    });
    var minusBtn = document.getElementById('sharesMinus');
    var plusBtn = document.getElementById('sharesPlus');
    if (minusBtn) minusBtn.addEventListener('click', function () { setSliderVal((parseInt(inputEl.value, 10) || 1) - 1); });
    if (plusBtn) plusBtn.addEventListener('click', function () { setSliderVal((parseInt(inputEl.value, 10) || 0) + 1); });
}

/** Shares 옆 가격 카드: UP/DOWN 비율(¢), 예상 거래액 갱신 */
var _sharesPriceDebounce = null;
function updateSharesPriceDisplay() {
    var topicId = window.currentOpinionTopicId;
    var sharesEl = document.getElementById('manualSharesInput');
    var shares = (sharesEl && parseInt(sharesEl.value, 10)) || 10;
    shares = Math.max(1, Math.min(1000, shares));
    var ratioEl = document.getElementById('sharesPriceRatio');
    var totalEl = document.getElementById('sharesPriceTotal');
    if (!ratioEl || !totalEl) return;
    if (!topicId) {
        ratioEl.innerHTML = '— : —';
        totalEl.textContent = '1시간 마켓 불러오기 후 표시';
        return;
    }
    var url = '/api/opinion/manual-trade/status?topic_id=' + encodeURIComponent(topicId) + '&shares=' + shares;
    fetchWithAuth(url)
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var up = data.maker_price_up != null ? Number(data.maker_price_up) : null;
            if (up == null) {
                ratioEl.innerHTML = '— : —';
                totalEl.textContent = '—';
                if (window.currentOpinionTradeDirection !== undefined) window.currentOpinionTradeDirection = null;
                if (window.currentOpinionGapUsd !== undefined) window.currentOpinionGapUsd = null;
                var gapEl = document.getElementById('sharesGapText');
                if (gapEl) { gapEl.textContent = '—'; gapEl.className = 'gap-value'; }
                return;
            }
            var down = 1 - up;
            var upC = Math.round(up * 100);
            var downC = Math.round(down * 100);
            ratioEl.innerHTML = '<span class="down">' + downC + '¢</span> : <span class="up">' + upC + '¢</span>';
            var preview = data.strategy_preview;
            var total = preview && preview.total_investment != null ? preview.total_investment : (shares * 1.0);
            totalEl.textContent = '≈ $' + (typeof total === 'number' ? total.toFixed(2) : total);
            // GAP / Maker 방향 저장 및 표시 (수동 Go! 시 서버 추천 방향 전달용)
            window.currentOpinionTradeDirection = data.trade_direction || null;
            window.currentOpinionGapUsd = data.btc_gap_usd != null ? Number(data.btc_gap_usd) : null;
            var gapEl = document.getElementById('sharesGapText');
            if (gapEl) {
                if (window.currentOpinionGapUsd != null && data.trade_direction) {
                    var gapStr = window.currentOpinionGapUsd >= 0 ? '+' + window.currentOpinionGapUsd.toFixed(0) : window.currentOpinionGapUsd.toFixed(0);
                    gapEl.textContent = '$' + gapStr + ' → Maker ' + data.trade_direction;
                    gapEl.className = 'gap-value ' + (data.trade_direction === 'UP' ? 'gap-up' : 'gap-down');
                } else {
                    gapEl.textContent = data.trade_direction ? 'Maker ' + data.trade_direction : '—';
                    gapEl.className = 'gap-value';
                }
            }
        })
        .catch(function () {
            ratioEl.innerHTML = '— : —';
            totalEl.textContent = '—';
        });
}

function setLastTradeState(state, message) {
    var img = document.getElementById('lastTradePepeImg');
    var wrap = document.getElementById('lastTradePepeWrap');
    var title = document.getElementById('lastTradeCardTitle');
    var statusText = document.getElementById('lastTradeStatusText');
    var card = document.getElementById('lastTradeCard');
    if (!img || !wrap || !statusText) return;
    var s = (state || 'unknown').toLowerCase();
    if (s !== 'success' && s !== 'fail' && s !== 'black_swan') s = 'unknown';
    var titles = { success: '직전 거래 성공 여부', fail: '직전 거래 성공 여부', black_swan: '직전 거래 성공 여부', unknown: '직전 거래 성공 여부' };
    img.src = LAST_TRADE_PEPE_IMAGES[s];
    img.alt = s === 'success' ? '성공' : s === 'fail' ? '실패' : s === 'black_swan' ? '블랙스완' : '정보없음';
    wrap.className = 'pepe-wrap state-' + s.replace('_', '-');
    if (title) title.textContent = titles[s];
    statusText.textContent = message || (s === 'unknown' ? '아직 거래 결과가 없습니다.' : '');
    if (card) card.setAttribute('data-state', s);
}

async function fetchWithAuth(url, options = {}) {
    const opts = { credentials: 'include', ...options };
    const res = await fetch(url, opts);
    if (res.status === 401) {
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    return res;
}

function showProxyAlert(show) {
    const el = document.getElementById('proxyAlert');
    if (el) el.style.display = show ? 'block' : 'none';
}

function renderAccounts(accounts) {
    const list = document.getElementById('opinionAccountsList');
    const countEl = document.getElementById('accountCount');
    if (!list) return;
    countEl.textContent = (accounts || []).length;
    if (!accounts || accounts.length === 0) {
        list.innerHTML = '<p class="empty-state">등록된 계정이 없습니다. "계정 로그인"으로 추가하세요.</p>';
        return;
    }
    list.innerHTML = accounts.map(function (a) {
        const defaultBadge = a.is_default ? '<span class="badge-default">Wallet 01</span>' : '';
        const eoaShort = (a.eoa || '').slice(0, 10) + '...' + (a.eoa || '').slice(-8);
        const displayName = a.name ? (a.name + ' (' + eoaShort + ')') : eoaShort;
        const flag = (a.flag_emoji || '').trim() ? '<span class="account-flag" title="프록시 국가">' + a.flag_emoji + '</span>' : '';
        return (
            '<div class="opinion-account-card">' +
            '<span class="account-id">#' + a.id + '</span>' +
            '<div><span class="account-name">' + displayName + '</span> ' + defaultBadge + '</div>' +
            '<span class="account-proxy-cell">' + flag + (flag && a.proxy_preview ? ' ' : '') + '<span class="proxy-preview">' + (a.proxy_preview || '') + '</span></span>' +
            '</div>'
        );
    }).join('');
}

function showLoginResult(data) {
    const section = document.getElementById('loginResultSection');
    const eoaEl = document.getElementById('loginResultEoa');
    const posEl = document.getElementById('loginResultPositions');
    const tradeEl = document.getElementById('loginResultTrades');
    if (!section) return;
    section.style.display = 'block';
    eoaEl.textContent = 'EOA: ' + (data.eoa || '');
    posEl.textContent = JSON.stringify(data.positions || {}, null, 2);
    tradeEl.textContent = JSON.stringify(data.trades || {}, null, 2);
}

async function loadOpinionAccounts() {
    try {
        const [statusRes, accountsRes] = await Promise.all([
            fetchWithAuth('/api/opinion/proxy-status'),
            fetchWithAuth('/api/opinion/accounts')
        ]);
        const status = await statusRes.json();
        const data = await accountsRes.json();
        showProxyAlert(!status.has_proxy);
        if (data.success && data.accounts) {
            renderAccounts(data.accounts);
        } else {
            renderAccounts([]);
        }
    } catch (e) {
        console.error(e);
        renderAccounts([]);
    }
}

function openLoginModal() {
    const modal = document.getElementById('opinionLoginModal');
    const pkInput = document.getElementById('opinionPK');
    if (modal && pkInput) {
        document.getElementById('opinionName') && (document.getElementById('opinionName').value = '');
        pkInput.value = '';
        modal.style.display = 'flex';
    }
}

function closeLoginModal() {
    const modal = document.getElementById('opinionLoginModal');
    if (modal) modal.style.display = 'none';
}

async function submitOpinionLogin(e) {
    e.preventDefault();
    const pk = (document.getElementById('opinionPK') && document.getElementById('opinionPK').value || '').trim();
    const name = (document.getElementById('opinionName') && document.getElementById('opinionName').value || '').trim();
    if (!pk) return;
    const submitBtn = e.target && e.target.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = '로그인 중...';
    }
    try {
        const res = await fetchWithAuth('/api/opinion/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ private_key: pk, name: name || undefined })
        });
        const data = await res.json();
        if (data.success) {
            closeLoginModal();
            loadOpinionAccounts();
            showLoginResult(data);
        } else {
            alert(data.error || '로그인 실패');
        }
    } catch (err) {
        alert('오류: ' + err.message);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = '로그인';
        }
    }
}

function setResultBox(id, content, isError) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = content || '';
    el.classList.toggle('empty', !content);
    if (isError) el.style.background = '#f8d7da';
    else el.style.background = '#f5f5f5';
}

function formatTimestamp(ts) {
    if (ts == null || ts === '') return '-';
    var t = parseInt(ts, 10);
    if (t > 1e12) t = Math.floor(t / 1000);
    var d = new Date(t * 1000);
    return d.toLocaleString('ko-KR', { dateStyle: 'medium', timeStyle: 'short' });
}

function renderBtcUpDownCard(data) {
    var wrap = document.getElementById('btcUpDownResult');
    if (!wrap) return;
    wrap.classList.remove('api-result-box');
    var m = data.result || {};
    var topicId = data.topicId || m.marketId || '-';
    var title = data.marketTitleDisplay || m.marketTitle || '-';
    var thumb = (m.thumbnailUrl || '').trim();
    var vol = m.volume != null ? String(m.volume) : '-';
    // 1시간 구간: collection.current.startTime/endTime 우선, 없으면 종료 1시간 전을 시작으로 표시
    var startLabel = '시작';
    var endLabel = '종료';
    var startTs = null;
    var endTs = m.cutoffAt;
    var cur = m.collection && m.collection.current;
    if (cur && (cur.startTime != null || cur.endTime != null)) {
        startTs = cur.startTime != null ? cur.startTime : (cur.endTime != null ? cur.endTime - 3600 : null);
        endTs = cur.endTime != null ? cur.endTime : m.cutoffAt;
    }
    if (startTs == null && endTs != null) {
        var endSec = parseInt(endTs, 10);
        if (endSec > 1e12) endSec = Math.floor(endSec / 1000);
        startTs = endSec - 3600;
        startLabel = '시작(추정 1h)';
    }
    var startStr = startTs != null ? formatTimestamp(startTs) : (formatTimestamp(m.createdAt) + ' (레코드 생성)');
    var endStr = endTs != null ? formatTimestamp(endTs) : '-';
    var imgHtml = thumb
        ? '<div class="btc-card-img-wrap"><img src="' + thumb.replace(/"/g, '&quot;') + '" alt="" onerror="this.parentElement.classList.add(\'failed\')"><div class="btc-card-img-placeholder">No image</div></div>'
        : '<div class="btc-card-img-placeholder">No image</div>';
    window.currentOpinionTopicId = topicId;
    wrap.innerHTML =
        '<div class="btc-market-card">' +
        '<div>' + imgHtml + '</div>' +
        '<div class="info">' +
        '<span class="topic-id">topicId: ' + topicId + '</span>' +
        '<div class="title">' + title + '</div>' +
        '<div class="row"><strong>' + startLabel + ':</strong> ' + startStr + '</div>' +
        '<div class="row"><strong>' + endLabel + ':</strong> ' + endStr + '</div>' +
        '<div class="row"><strong>거래량:</strong> ' + vol + '</div>' +
        '</div></div>';
    updateSharesPriceDisplay();
}

async function loadBtcUpDown() {
    var box = document.getElementById('btcUpDownResult');
    if (!box) return;
    box.innerHTML = '불러오는 중...';
    box.classList.add('api-result-box');
    try {
        var res = await fetchWithAuth('/api/opinion/btc-up-down');
        var text = await res.text();
        var data;
        try {
            data = JSON.parse(text);
        } catch (parseErr) {
            var preview = text.length > 150 ? text.slice(0, 150) + '...' : text;
            box.innerHTML = '서버 응답 오류 (JSON 아님). 상태: ' + res.status + '\n\n응답 미리보기:\n' + preview.replace(/</g, '&lt;').replace(/>/g, '&gt;');
            box.style.background = '#f8d7da';
            box.style.whiteSpace = 'pre-wrap';
            return;
        }
        if (data.success && (data.result !== undefined || data.topicId)) {
            renderBtcUpDownCard(data);
        } else {
            box.innerHTML = data.error || '실패';
            box.style.background = '#f8d7da';
        }
    } catch (e) {
        box.innerHTML = '오류: ' + e.message;
        box.style.background = '#f8d7da';
    }
}

function updateBtcPriceGapCard() {
    var card = document.getElementById('btcPriceGapCard');
    var errEl = document.getElementById('btcPriceGapError');
    var placeholder = document.getElementById('btcPriceGapPlaceholder');
    var nameEl = document.getElementById('btcGapMarketName');
    var startEl = document.getElementById('btcGapStartPrice');
    var currentEl = document.getElementById('btcGapCurrentPrice');
    var gapEl = document.getElementById('btcGapGap');
    if (!card || !gapEl) return;
    fetchWithAuth('/api/opinion/btc-price-gap')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                if (placeholder) placeholder.style.display = 'none';
                if (errEl) errEl.style.display = 'none';
                card.style.display = 'block';
                if (nameEl) nameEl.textContent = data.marketTitleDisplay || data.marketTitle || 'BTC Up or Down - Hourly';
                if (startEl) startEl.textContent = '$' + (data.startPrice != null ? Number(data.startPrice).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
                if (currentEl) currentEl.textContent = '$' + (data.currentPrice != null ? Number(data.currentPrice).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
                var gap = data.gap != null ? Number(data.gap) : null;
                gapEl.textContent = gap != null ? (gap >= 0 ? '+' : '') + gap.toFixed(2) : '—';
                gapEl.classList.remove('gap-up', 'gap-down', 'gap-zero');
                if (gap != null) {
                    if (gap > 0) gapEl.classList.add('gap-up');
                    else if (gap < 0) gapEl.classList.add('gap-down');
                    else gapEl.classList.add('gap-zero');
                }
            } else {
                card.style.display = 'none';
                if (placeholder) placeholder.style.display = 'block';
                if (errEl) {
                    errEl.textContent = data.error || '시세 조회 실패';
                    errEl.style.display = 'block';
                }
            }
        })
        .catch(function () {
            card.style.display = 'none';
            if (placeholder) placeholder.style.display = 'block';
            if (errEl) {
                errEl.textContent = '연결 오류. 잠시 후 다시 시도해 주세요.';
                errEl.style.display = 'block';
            }
        });
}

var overallChartInstance = null;

function loadOverallChart(metric, range) {
    var canvas = document.getElementById('overallChart');
    var placeholder = document.getElementById('overallChartPlaceholder');
    if (!canvas) return;
    if (placeholder) { placeholder.style.display = 'block'; }
    var url = '/api/opinion/overall?metric=' + encodeURIComponent(metric) + '&range=' + encodeURIComponent(range);
    fetchWithAuth(url)
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (placeholder) placeholder.style.display = 'none';
            if (!res.success || !res.labels) {
                if (overallChartInstance) { overallChartInstance.data.labels = []; overallChartInstance.data.datasets[0].data = []; overallChartInstance.update(); }
                return;
            }
            var labels = res.labels;
            var data = res.data || [];
            if (typeof Chart === 'undefined') return;
            if (overallChartInstance) {
                overallChartInstance.data.labels = labels;
                overallChartInstance.data.datasets[0].data = data;
                overallChartInstance.data.datasets[0].label = metric === 'usdt' ? 'USDT 총합 ($)' : '총 거래량';
                overallChartInstance.options.scales.y.beginAtZero = true;
                overallChartInstance.update();
                return;
            }
            overallChartInstance = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{ label: metric === 'usdt' ? 'USDT 총합 ($)' : '총 거래량', data: data, backgroundColor: 'rgba(102, 126, 234, 0.6)', borderColor: 'rgba(102, 126, 234, 1)', borderWidth: 1 }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } }
                }
            });
        })
        .catch(function () {
            if (placeholder) { placeholder.style.display = 'none'; }
            if (overallChartInstance) { overallChartInstance.data.labels = []; overallChartInstance.data.datasets[0].data = []; overallChartInstance.update(); }
        });
}

function initOverallCard() {
    var card = document.getElementById('overallCard');
    if (!card) return;
    var currentMetric = 'volume';
    var currentRange = '6h';
    card.querySelectorAll('.overall-btn[data-metric]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            card.querySelectorAll('.overall-btn[data-metric]').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentMetric = btn.getAttribute('data-metric');
            loadOverallChart(currentMetric, currentRange);
        });
    });
    card.querySelectorAll('.overall-btn[data-range]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            card.querySelectorAll('.overall-btn[data-range]').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentRange = btn.getAttribute('data-range');
            loadOverallChart(currentMetric, currentRange);
        });
    });
    loadOverallChart(currentMetric, currentRange);
}

document.addEventListener('DOMContentLoaded', function () {
    loadOpinionAccounts();
    loadBtcUpDown();
    updateBtcPriceGapCard();
    setLastTradeState('unknown', '아직 거래 결과가 없습니다.');
    initSharesSlider();
    updateSharesPriceDisplay();
    initOverallCard();
    setInterval(updateBtcPriceGapCard, 3000);
    document.getElementById('btnAddAccount') && document.getElementById('btnAddAccount').addEventListener('click', openLoginModal);
    document.getElementById('btnLoadBtcUpDown') && document.getElementById('btnLoadBtcUpDown').addEventListener('click', function () { loadBtcUpDown(); updateBtcPriceGapCard(); });
    document.querySelector('#opinionLoginModal .modal-overlay') && document.querySelector('#opinionLoginModal .modal-overlay').addEventListener('click', closeLoginModal);
    document.getElementById('opinionLoginForm') && document.getElementById('opinionLoginForm').addEventListener('submit', submitOpinionLogin);
    document.getElementById('btnAutoGo') && document.getElementById('btnAutoGo').addEventListener('click', runAutoGo);
    document.getElementById('btnAutoStop') && document.getElementById('btnAutoStop').addEventListener('click', runAutoStop);
    document.getElementById('btnManualGo') && document.getElementById('btnManualGo').addEventListener('click', runManualGo);
    setInterval(loadBtcUpDown, 3600000);
    pollOpinionAutoStats();
    setInterval(pollOpinionAutoStats, 5000);
});

function runAutoGo() {
    var btn = document.getElementById('btnAutoGo');
    var sharesEl = document.getElementById('manualSharesInput');
    var shares = (sharesEl && parseInt(sharesEl.value, 10)) || 10;
    shares = Math.max(1, shares);
    if (btn) { btn.disabled = true; btn.textContent = '확인 중...'; }
    fetchWithAuth('/api/opinion/auto/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shares: shares })
    })
        .then(function (r) { return r.json().then(function (data) { return { status: r.status, data: data }; }); })
        .then(function (res) {
            var data = res.data;
            var msg = (data && data.error) ? data.error : (data && data.user_message) ? data.user_message : '자동 Go!를 시작할 수 없습니다.';
            if (data && data.success) {
                alert('자동 거래가 시작되었습니다. (Shares: ' + shares + ')');
                pollOpinionAutoStats();
            } else {
                alert(msg);
            }
        })
        .catch(function (e) {
            alert('연결 오류: ' + (e.message || e));
        })
        .finally(function () {
            if (btn) { btn.disabled = false; btn.textContent = '자동 Go!'; }
        });
}

function runAutoStop() {
    var btn = document.getElementById('btnAutoStop');
    if (btn) btn.disabled = true;
    fetchWithAuth('/api/opinion/auto/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data && data.success) alert('자동 거래를 중지했습니다.');
            pollOpinionAutoStats();
        })
        .catch(function (e) { alert('연결 오류: ' + (e.message || e)); })
        .finally(function () {
            if (btn) { btn.disabled = false; pollOpinionAutoStats(); }
        });
}

function pollOpinionAutoStats() {
    fetchWithAuth('/api/opinion/auto/stats')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data || !data.success || !data.stats) return;
            var s = data.stats;
            var goBtn = document.getElementById('btnAutoGo');
            var stopBtn = document.getElementById('btnAutoStop');
            var statusEl = document.getElementById('autoStatusText');
            if (s.is_running) {
                if (goBtn) goBtn.style.display = 'none';
                if (stopBtn) { stopBtn.style.display = 'inline-block'; stopBtn.disabled = false; }
                if (statusEl) statusEl.textContent = '자동 거래 중 (성공 ' + (s.successful_trades || 0) + ' / 실패 ' + (s.failed_trades || 0) + ')';
            } else {
                if (goBtn) goBtn.style.display = 'inline-block';
                if (stopBtn) stopBtn.style.display = 'none';
                if (statusEl) statusEl.textContent = (s.total_trades > 0) ? ('대기 중 (총 ' + s.total_trades + '회)') : '';
            }
            var last = s.last_result;
            if (last && typeof setLastTradeState === 'function') {
                if (last.success) setLastTradeState('success', '자전 성공. 수수료 없이 정리됨.');
                else if (last.needs_clob) setLastTradeState('fail', last.error || 'CLOB 미연동');
                else setLastTradeState('fail', last.error || '실패');
            }
        })
        .catch(function () {});
}

/** 수동 Go!: Shares만 입력, 방향·Maker/Taker는 서버에서 자동 설정 */
function runManualGo() {
    var sharesEl = document.getElementById('manualSharesInput');
    var shares = (sharesEl && parseInt(sharesEl.value, 10)) || 10;
    shares = Math.max(1, shares);
    var btn = document.getElementById('btnManualGo');
    if (btn) { btn.disabled = true; btn.textContent = '실행 중...'; }
    var resultEl = document.getElementById('manualTradeResult');
    var body = { shares: shares };
    if (window.currentOpinionTopicId) body.topic_id = window.currentOpinionTopicId;
    // 서버 추천 방향(GAP 기준) 전달 — 불러오기/Shares 변경 시 갱신된 trade_direction 사용
    if (window.currentOpinionTradeDirection) body.direction = window.currentOpinionTradeDirection;
    fetchWithAuth('/api/opinion/manual-trade/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (resultEl) {
                resultEl.style.display = 'block';
                if (data.success) {
                    resultEl.className = 'manual-trade-result success';
                    resultEl.textContent = '실행 완료. 방향 ' + (data.direction || '') + ', Maker: ' + (data.maker_order_id || '-') + ', Taker: ' + (data.taker_order_id || '-');
                    if (typeof setLastTradeState === 'function') setLastTradeState('success', '자전 성공. 수수료 없이 정리됨.');
                } else {
                    resultEl.className = 'manual-trade-result ' + (data.needs_clob ? 'info' : 'error');
                    resultEl.textContent = data.error || '실패';
                    if (typeof setLastTradeState === 'function') setLastTradeState('fail', data.error || (data.needs_clob ? 'CLOB 미연동' : '실패'));
                }
            }
        })
        .catch(function (err) {
            if (resultEl) {
                resultEl.style.display = 'block';
                resultEl.className = 'manual-trade-result error';
                resultEl.textContent = '오류: ' + (err.message || err);
            }
        })
        .finally(function () {
            if (btn) { btn.disabled = false; btn.textContent = '수동 Go!'; }
        });
}
