// Opinion.trade 다중 로그인 UI

async function fetchWithAuth(url, options = {}) {
    const res = await fetch(url, options);
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
        return (
            '<div class="opinion-account-card">' +
            '<span class="account-id">#' + a.id + '</span>' +
            '<div><span class="eoa">' + (a.eoa || '').slice(0, 10) + '...' + (a.eoa || '').slice(-8) + '</span> ' + defaultBadge + '</div>' +
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
            body: JSON.stringify({ private_key: pk })
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

document.addEventListener('DOMContentLoaded', function () {
    loadOpinionAccounts();
    document.getElementById('btnAddAccount') && document.getElementById('btnAddAccount').addEventListener('click', openLoginModal);
    document.getElementById('opinionLoginCancel') && document.getElementById('opinionLoginCancel').addEventListener('click', closeLoginModal);
    document.querySelector('#opinionLoginModal .modal-overlay') && document.querySelector('#opinionLoginModal .modal-overlay').addEventListener('click', closeLoginModal);
    document.getElementById('opinionLoginForm') && document.getElementById('opinionLoginForm').addEventListener('submit', submitOpinionLogin);
});
