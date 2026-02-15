// Opinion.trade 다중 로그인 UI

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
        const defaultBadge = a.is_default ? '<span class="badge-default">디폴트</span>' : '';
        const eoaShort = (a.eoa || '').slice(0, 10) + '...' + (a.eoa || '').slice(-8);
        const displayName = a.name ? (a.name + ' (' + eoaShort + ')') : eoaShort;
        return (
            '<div class="opinion-account-card">' +
            '<span class="account-id">#' + a.id + '</span>' +
            '<div><span class="account-name">' + displayName + '</span> ' + defaultBadge + '</div>' +
            '<span style="font-size:0.8rem;color:#666">' + (a.proxy_preview || '') + '</span>' +
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
    var title = m.marketTitle || '-';
    var thumb = (m.thumbnailUrl || '').trim();
    var vol = m.volume != null ? String(m.volume) : '-';
    var created = formatTimestamp(m.createdAt);
    var cutoff = formatTimestamp(m.cutoffAt);
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
        '<div class="row"><strong>생성:</strong> ' + created + '</div>' +
        '<div class="row"><strong>종료:</strong> ' + cutoff + '</div>' +
        '<div class="row"><strong>거래량:</strong> ' + vol + '</div>' +
        '</div></div>';
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

document.addEventListener('DOMContentLoaded', function () {
    loadOpinionAccounts();
    loadBtcUpDown();
    document.getElementById('btnAddAccount') && document.getElementById('btnAddAccount').addEventListener('click', openLoginModal);
    document.getElementById('btnLoadBtcUpDown') && document.getElementById('btnLoadBtcUpDown').addEventListener('click', loadBtcUpDown);
    document.getElementById('opinionLoginCancel') && document.getElementById('opinionLoginCancel').addEventListener('click', closeLoginModal);
    document.querySelector('#opinionLoginModal .modal-overlay') && document.querySelector('#opinionLoginModal .modal-overlay').addEventListener('click', closeLoginModal);
    document.getElementById('opinionLoginForm') && document.getElementById('opinionLoginForm').addEventListener('submit', submitOpinionLogin);
    document.getElementById('btnAutoGo') && document.getElementById('btnAutoGo').addEventListener('click', function () { alert('자동 Go! (기능 연동 예정)'); });
    document.getElementById('btnManualGo') && document.getElementById('btnManualGo').addEventListener('click', openManualTradeModal);
    document.getElementById('manualTradeCancel') && document.getElementById('manualTradeCancel').addEventListener('click', closeManualTradeModal);
    document.querySelector('#manualTradeModal .modal-overlay') && document.querySelector('#manualTradeModal .modal-overlay').addEventListener('click', closeManualTradeModal);
    document.getElementById('manualTradeForm') && document.getElementById('manualTradeForm').addEventListener('submit', submitManualTrade);
    setInterval(loadBtcUpDown, 3600000);
});

function closeManualTradeModal() {
    var modal = document.getElementById('manualTradeModal');
    if (modal) modal.style.display = 'none';
}

function openManualTradeModal() {
    var topicId = window.currentOpinionTopicId;
    if (!topicId) {
        alert('먼저 "불러오기"로 1시간 마켓을 불러와 주세요.');
        return;
    }
    var modal = document.getElementById('manualTradeModal');
    var topicInput = document.getElementById('manualTopicId');
    if (topicInput) topicInput.value = topicId;
    var sharesInput = document.getElementById('manualShares');
    if (sharesInput) sharesInput.value = 10;
    fetchWithAuth('/api/opinion/manual-trade/status?topic_id=' + topicId + '&shares=10')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error && !data.topic_id) {
                alert(data.error || '상태 조회 실패');
                return;
            }
            if (!data.trade_ready) {
                alert(data.trade_reason || '거래 대기 중');
                return;
            }
            fillManualTradeAccounts();
            if (modal) modal.style.display = 'flex';
        })
        .catch(function (e) {
            alert('조회 오류: ' + (e.message || e));
        });
}

function fillManualTradeAccounts() {
    fetchWithAuth('/api/opinion/accounts')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var accounts = (data.accounts || []);
            var makerSel = document.getElementById('manualMakerAccount');
            var takerSel = document.getElementById('manualTakerAccount');
            if (!makerSel || !takerSel) return;
            makerSel.innerHTML = '';
            takerSel.innerHTML = '';
            accounts.forEach(function (a) {
                var label = (a.name || a.eoa) ? (a.name || '') + ' ' + (a.eoa || '').slice(0, 8) + '...' : '#' + a.id;
                makerSel.appendChild(new Option(label, a.id));
                takerSel.appendChild(new Option(label, a.id));
            });
            if (accounts.length >= 2) {
                makerSel.value = accounts[0].id;
                takerSel.value = accounts[1].id;
            }
        });
}

function submitManualTrade(e) {
    e.preventDefault();
    var topicId = parseInt(document.getElementById('manualTopicId').value, 10);
    var shares = parseInt(document.getElementById('manualShares').value, 10) || 10;
    var direction = (document.getElementById('manualDirection') && document.getElementById('manualDirection').value) || 'UP';
    var makerId = document.getElementById('manualMakerAccount') && document.getElementById('manualMakerAccount').value;
    var takerId = document.getElementById('manualTakerAccount') && document.getElementById('manualTakerAccount').value;
    var btn = document.getElementById('manualTradeSubmit');
    if (btn) { btn.disabled = true; btn.textContent = '실행 중...'; }
    var resultEl = document.getElementById('manualTradeResult');
    fetchWithAuth('/api/opinion/manual-trade/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            topic_id: topicId,
            shares: shares,
            direction: direction,
            maker_account_id: makerId ? parseInt(makerId, 10) : undefined,
            taker_account_id: takerId ? parseInt(takerId, 10) : undefined
        })
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (resultEl) {
                resultEl.style.display = 'block';
                if (data.success) {
                    resultEl.className = 'manual-trade-result success';
                    resultEl.textContent = '실행 완료. Maker: ' + (data.maker_order_id || '-') + ', Taker: ' + (data.taker_order_id || '-');
                } else {
                    resultEl.className = 'manual-trade-result ' + (data.needs_clob ? 'info' : 'error');
                    resultEl.textContent = data.error || '실패';
                }
            }
            if (data.success) closeManualTradeModal();
        })
        .catch(function (err) {
            if (resultEl) {
                resultEl.style.display = 'block';
                resultEl.className = 'manual-trade-result error';
                resultEl.textContent = '오류: ' + (err.message || err);
            }
        })
        .finally(function () {
            if (btn) { btn.disabled = false; btn.textContent = '실행'; }
        });
}
