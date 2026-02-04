// 경봇 Dashboard JavaScript

// 세션 만료 시 로그인 페이지로 리다이렉트
async function fetchWithAuth(url, options = {}) {
    const res = await fetch(url, options);
    if (res.status === 401) {
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    return res;
}

class GyeongBot {
    constructor() {
        this.currentMarket = null;
        this.accounts = [];
        this.autoMode = false;
        this.updateInterval = null;
        this.statsInterval = null;
        
        this.init();
    }
    
    init() {
        // Load initial data
        this.loadAccounts();
        this.loadCurrentMarket();
        
        // Set up event listeners
        document.getElementById('executeBtn').addEventListener('click', () => this.executeTrade());
        document.getElementById('autoToggleBtn').addEventListener('click', () => this.toggleAutoMode());
        const refreshBtn = document.getElementById('floatingRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refresh());
        }
        document.getElementById('addAccountCancel')?.addEventListener('click', () => this.closeAddAccountModal());
        document.querySelector('#addAccountModal .modal-overlay')?.addEventListener('click', () => this.closeAddAccountModal());
        document.getElementById('addAccountForm')?.addEventListener('submit', (e) => this.submitAddAccount(e));
        document.getElementById('sharesInput').addEventListener('input', () => {
            this.updateTradeEstimate();
            clearTimeout(this._sharesDebounce);
            this._sharesDebounce = setTimeout(() => this.loadCurrentMarket(), 500);
        });
        
        // Start auto-update (every 5 seconds)
        this.updateInterval = setInterval(() => {
            this.loadCurrentMarket();
        }, 5000);
    }
    
    async loadAccounts() {
        try {
            const response = await fetchWithAuth('/api/status');
            const data = await response.json();
            
            if (data.success) {
                this.accounts = data.accounts;
                this.renderAccounts();
                document.getElementById('accountCount').textContent = data.total_accounts;
            }
        } catch (error) {
            console.error('Failed to load accounts:', error);
        }
    }
    
    async refresh() {
        await Promise.all([this.loadCurrentMarket(), this.loadAccounts()]);
    }

    async loadCurrentMarket() {
        try {
            const shares = parseInt(document.getElementById('sharesInput')?.value) || 10;
            const response = await fetchWithAuth(`/api/market/current?shares=${shares}`);
            const data = await response.json();
            
            if (data.success && data.market) {
                this.currentMarket = data.market;
                this.renderMarket();
                this.renderExecutionPreview(data.market);
                this.updateTradeEstimate();
            } else {
                this.renderNoMarket();
                this.renderExecutionPreview(null);
            }
        } catch (error) {
            console.error('Failed to load market:', error);
            this.renderNoMarket();
            this.renderExecutionPreview(null);
        }
    }
    
    renderMarket() {
        const market = this.currentMarket;
        const card = document.getElementById('marketCard');
        
        const gap = market.price_gap ?? 0;
        const gapColor = gap >= 0 ? '#28a745' : '#dc3545';
        const gapSign = gap >= 0 ? '+' : '';
        
        card.innerHTML = `
            <h3>${market.title}</h3>
            <div class="market-info">
                <div class="info-item">
                    <label>Price to Beat (기준가)</label>
                    <value>$${market.start_price.toLocaleString()}</value>
                </div>
                <div class="info-item info-item-gap">
                    <label>가격 갭 (vs Price to Beat)</label>
                    <value style="color: ${gapColor}">${gapSign}$${gap.toLocaleString()}</value>
                </div>
                <div class="info-item">
                    <label>남은 시간</label>
                    <value>${this.formatTime(market.time_remaining)}</value>
                </div>
                <div class="info-item">
                    <label>YES 가격 (매수)</label>
                    <value>${market.yes_price != null ? '$' + Number(market.yes_price).toFixed(2) : '—'}</value>
                </div>
                <div class="info-item">
                    <label>NO 가격 (매수)</label>
                    <value>${market.no_price != null ? '$' + Number(market.no_price).toFixed(2) : '—'}</value>
                </div>
            </div>
            <div class="${market.trade_ready ? 'trade-ready' : 'trade-not-ready'}">
                <strong>${market.trade_ready ? '✅ 거래 가능' : '⏳ 대기 중'}</strong>
                ${market.trade_direction ? ` - ${market.trade_direction}` : ''}
                <br>
                <small>${market.trade_reason}</small>
            </div>
        `;
        
        // Enable/disable execute button
        const executeBtn = document.getElementById('executeBtn');
        executeBtn.disabled = !market.trade_ready;
    }
    
    renderExecutionPreview(market) {
        const placeholder = document.getElementById('executionPlaceholder');
        const details = document.getElementById('executionDetails');
        if (!placeholder || !details) return;
        
        const preview = market?.strategy_preview;
        if (!preview || preview.status !== 'arbitrage_ready' || !preview.maker) {
            placeholder.style.display = 'block';
            details.style.display = 'none';
            placeholder.textContent = market 
                ? (preview?.status_message || '거래 조건 충족 시 실행 예정 정보가 표시됩니다')
                : '거래 조건 충족 시 실행 예정 정보가 표시됩니다';
            return;
        }
        
        const m = preview.maker;
        const t = preview.taker;
        const makerAcc = m.account_id != null ? `계정 ${m.account_id}` : 'Maker 계정';
        const takerAcc = t.account_id != null ? `계정 ${t.account_id}` : 'Taker 계정';
        placeholder.style.display = 'none';
        details.style.display = 'block';
        details.innerHTML = `
            <h4>실행 시 수행될 거래</h4>
            <div class="execution-row">
                <span>Maker ${m.side}</span>
                <span>${makerAcc} → Limit ${m.price_display} × ${m.shares} shares = $${m.investment.toFixed(2)}</span>
            </div>
            <div class="execution-row">
                <span>Taker ${t.side}</span>
                <span>${takerAcc} → $${t.investment.toFixed(2)}</span>
            </div>
            <div class="execution-row execution-total">
                <span>총 투자</span>
                <span>$${preview.total_investment.toFixed(2)}</span>
            </div>
            <div class="execution-row">
                <span>예상 수수료</span>
                <span>-$${preview.guaranteed_loss.toFixed(4)}</span>
            </div>
        `;
    }
    
    renderNoMarket() {
        const card = document.getElementById('marketCard');
        if (card) {
            card.innerHTML = `
                <p style="text-align: center; color: #999; padding: 40px;">
                    활성 마켓이 없습니다
                </p>
            `;
        }
        const executeBtn = document.getElementById('executeBtn');
        if (executeBtn) executeBtn.disabled = true;
    }
    
    renderAccounts() {
        const list = document.getElementById('accountsList');
        const addBtn = document.getElementById('addAccountBtn');
        if (addBtn) addBtn.onclick = () => this.openAddAccountModal();
        
        if (this.accounts.length === 0) {
            list.innerHTML = '<p class="empty-state">계정이 없습니다. "+ 계정 추가"로 PK와 프록시를 입력하세요.</p>';
            return;
        }
        
        list.innerHTML = this.accounts.map(account => `
            <div class="account-card">
                <div class="account-id">#${account.id}</div>
                <div class="account-info">
                    <div class="account-address">${account.address ? account.address.substring(0, 10) + '...' : 'N/A'}</div>
                    <div>${account.username || 'Unknown'}</div>
                </div>
                <div class="account-balance">$${account.balance.toFixed(2)}</div>
                <div class="account-status ${account.is_logged_in ? 'status-active' : 'status-inactive'}">
                    ${account.is_logged_in ? 'Active' : 'Inactive'}
                </div>
            </div>
        `).join('');
    }
    
    openAddAccountModal() {
        if (this.accounts.length >= 3) {
            this.showStatus('프록시를 추가해 주세요. 계정은 최대 3개까지 가능합니다.', 'error');
            return;
        }
        const modal = document.getElementById('addAccountModal');
        const form = document.getElementById('addAccountForm');
        if (modal && form) {
            form.reset();
            modal.style.display = 'flex';
        }
    }
    
    closeAddAccountModal() {
        const modal = document.getElementById('addAccountModal');
        if (modal) modal.style.display = 'none';
    }
    
    async submitAddAccount(e) {
        e.preventDefault();
        const slot = parseInt(document.getElementById('addAccountSlot')?.value) || 1;
        const pk = (document.getElementById('addAccountPK')?.value || '').trim();
        const proxy = (document.getElementById('addAccountProxy')?.value || '').trim();
        if (!pk || !proxy) {
            this.showStatus('PK와 프록시를 모두 입력하세요.', 'error');
            return;
        }
        try {
            const res = await fetchWithAuth('/api/accounts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ slot, private_key: pk, proxy })
            });
            const data = await res.json();
            if (data.success) {
                this.closeAddAccountModal();
                this.showStatus('계정이 추가되었습니다.', 'success');
                this.loadAccounts();
            } else {
                this.showStatus(data.error || '계정 추가 실패', 'error');
            }
        } catch (err) {
            this.showStatus('오류: ' + err.message, 'error');
        }
    }
    
    updateTradeEstimate() {
        if (!this.currentMarket) return;
        
        const shares = parseInt(document.getElementById('sharesInput').value) || 0;
        const yesPrice = this.currentMarket.yes_price;
        const noPrice = this.currentMarket.no_price;
        
        const investment = (yesPrice * shares) + (noPrice * shares);
        const fee = investment * 0.002; // Approximate 0.2% taker fee
        
        document.getElementById('estimatedInvestment').textContent = `$${investment.toFixed(2)}`;
        document.getElementById('estimatedFee').textContent = `$${fee.toFixed(4)}`;
    }
    
    async executeTrade() {
        if (!this.currentMarket || !this.currentMarket.trade_ready) {
            this.showStatus('거래 조건이 충족되지 않았습니다', 'error');
            return;
        }
        
        const shares = parseInt(document.getElementById('sharesInput').value);
        if (shares < 1) {
            this.showStatus('유효한 Shares 수량을 입력하세요', 'error');
            return;
        }
        
        const executeBtn = document.getElementById('executeBtn');
        executeBtn.disabled = true;
        executeBtn.textContent = '거래 실행 중...';
        
        try {
            const response = await fetchWithAuth('/api/trade/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    market_id: this.currentMarket.id,
                    shares: shares,
                    direction: this.currentMarket.trade_direction
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showStatus('✅ 거래가 성공적으로 실행되었습니다!', 'success');
                this.addTradeToHistory(data);
            } else {
                this.showStatus(`❌ 거래 실패: ${data.error}`, 'error');
            }
            
        } catch (error) {
            this.showStatus(`❌ 오류: ${error.message}`, 'error');
        } finally {
            executeBtn.disabled = false;
            executeBtn.textContent = '거래 실행';
            this.loadAccounts(); // Refresh balances
        }
    }
    
    async toggleAutoMode() {
        const btn = document.getElementById('autoToggleBtn');
        const shares = parseInt(document.getElementById('sharesInput').value);
        
        if (!this.autoMode) {
            // Start auto mode
            btn.disabled = true;
            btn.textContent = '시작 중...';
            
            try {
                const response = await fetchWithAuth('/api/auto/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ shares })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    this.autoMode = true;
                    btn.textContent = '🛑 Auto 모드 중지';
                    btn.classList.add('active');
                    this.showStatus('🤖 Auto 모드 시작!', 'success');
                    
                    // Show stats section
                    document.getElementById('autoStats').style.display = 'block';
                    
                    // Start stats update
                    this.statsInterval = setInterval(() => this.updateAutoStats(), 3000);
                } else {
                    this.showStatus(`❌ Auto 모드 시작 실패: ${data.error}`, 'error');
                }
            } catch (error) {
                this.showStatus(`❌ 오류: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
            }
        } else {
            // Stop auto mode
            btn.disabled = true;
            btn.textContent = '중지 중...';
            
            try {
                const response = await fetchWithAuth('/api/auto/stop', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    this.autoMode = false;
                    btn.textContent = '🤖 Auto 모드 시작';
                    btn.classList.remove('active');
                    this.showStatus('🛑 Auto 모드 중지됨', 'error');
                    
                    // Stop stats update
                    if (this.statsInterval) {
                        clearInterval(this.statsInterval);
                    }
                } else {
                    this.showStatus(`❌ Auto 모드 중지 실패: ${data.error}`, 'error');
                }
            } catch (error) {
                this.showStatus(`❌ 오류: ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
            }
        }
    }
    
    async updateAutoStats() {
        try {
            const response = await fetchWithAuth('/api/auto/stats');
            const data = await response.json();
            
            if (data.success) {
                const stats = data.stats;
                
                document.getElementById('autoStatus').textContent = 
                    stats.is_running ? '▶️ 실행 중' : '⏸️ 정지됨';
                document.getElementById('totalTrades').textContent = stats.total_trades;
                document.getElementById('successfulTrades').textContent = stats.successful_trades;
                document.getElementById('failedTrades').textContent = stats.failed_trades;
                document.getElementById('successRate').textContent = 
                    `${stats.success_rate.toFixed(1)}%`;
            }
        } catch (error) {
            console.error('Failed to update auto stats:', error);
        }
    }
    
    checkAutoTrade() {
        // This is now handled by the backend auto_trader
        // No need for frontend auto trading logic
    }
    
    toggleAutoMode_old(enabled) {
        this.autoMode = enabled;
        if (enabled) {
            this.showStatus('🤖 Auto 모드 활성화', 'success');
        } else {
            this.showStatus('Auto 모드 비활성화', 'error');
        }
    }
    
    showStatus(message, type) {
        const statusEl = document.getElementById('statusMessage');
        statusEl.textContent = message;
        statusEl.className = `status-message ${type}`;
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            statusEl.className = 'status-message';
        }, 5000);
    }
    
    addTradeToHistory(trade) {
        const historyList = document.getElementById('historyList');
        
        // Remove empty state
        const emptyState = historyList.querySelector('.empty-state');
        if (emptyState) emptyState.remove();
        
        const timestamp = new Date().toLocaleString('ko-KR');
        const item = document.createElement('div');
        item.className = 'history-item';
        const price = trade.price != null ? trade.price.toFixed(2) : '?';
        item.innerHTML = `
            <div>${timestamp}</div>
            <div>${trade.direction || '?'} - ${trade.shares || 0} shares @ $${price}</div>
            <div>Maker: ${trade.maker_order || '?'}</div>
            <div>Taker: ${trade.taker_order || '?'}</div>
        `;
        
        historyList.insertBefore(item, historyList.firstChild);
    }
    
    formatTime(seconds) {
        if (seconds == null || isNaN(seconds) || seconds < 0) return '--:--';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.bot = new GyeongBot();
});
