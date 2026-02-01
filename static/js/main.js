// 경봇 Dashboard JavaScript

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
            const response = await fetch('/api/status');
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
    
    async loadCurrentMarket() {
        try {
            const shares = parseInt(document.getElementById('sharesInput')?.value) || 10;
            const response = await fetch(`/api/market/current?shares=${shares}`);
            const data = await response.json();
            
            if (data.success) {
                this.currentMarket = data.market;
                this.renderMarket();
                this.renderStrategyPreview(data.market);
                this.updateTradeEstimate();
            } else {
                this.renderNoMarket();
                this.hideStrategyPreview();
            }
        } catch (error) {
            console.error('Failed to load market:', error);
            this.renderNoMarket();
            this.hideStrategyPreview();
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
                    <label>시작 가격</label>
                    <value>$${market.start_price.toLocaleString()}</value>
                </div>
                <div class="info-item">
                    <label>현재 BTC 가격</label>
                    <value>$${market.current_btc_price.toLocaleString()}</value>
                </div>
                <div class="info-item">
                    <label>가격 갭</label>
                    <value style="color: ${gapColor}">${gapSign}$${gap.toLocaleString()}</value>
                </div>
                <div class="info-item">
                    <label>남은 시간</label>
                    <value>${this.formatTime(market.time_remaining)}</value>
                </div>
                <div class="info-item">
                    <label>YES 가격</label>
                    <value>$${market.yes_price.toFixed(2)}</value>
                </div>
                <div class="info-item">
                    <label>NO 가격</label>
                    <value>$${market.no_price.toFixed(2)}</value>
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
    
    renderStrategyPreview(market) {
        const container = document.getElementById('strategyPreview');
        if (!container) return;
        
        const preview = market?.strategy_preview;
        if (!preview) {
            container.style.display = 'none';
            return;
        }
        
        container.style.display = 'block';
        
        if (preview.status === 'arbitrage_ready' && preview.maker) {
            const lossRate = preview.loss_rate_pct ?? 0;
            const lossColor = lossRate === 0 ? '#28a745' : '#dc3545';
            container.innerHTML = `
                <div class="strategy-box status-pink">
                    <h4>▲ ${preview.status_message}</h4>
                </div>
                <div class="strategy-box status-yellow">
                    <h4>▲ 최소 손실 배분 (손실률 ${lossRate.toFixed(2)}%)</h4>
                    <p class="strategy-detail">차익거래 가능, Maker(수수료 0%) + Taker 조합으로 손실 최소화</p>
                </div>
                <div class="strategy-box status-gray">
                    <h4>💡 추천 전략</h4>
                    <p class="strategy-detail">${preview.recommended_strategy}</p>
                </div>
                <div class="strategy-box status-gray">
                    <h4>Maker ${preview.maker.side}</h4>
                    <div class="strategy-detail">Shares: ${preview.maker.shares} (Limit Price: ${preview.maker.price_display})</div>
                    <div class="strategy-row">배팅 금액: <span class="highlight">$${preview.maker.investment.toFixed(2)}</span></div>
                    <div class="strategy-detail">✓ ${preview.maker.side} 적중시: +$${preview.maker.profit_if_win.toFixed(2)} 수익</div>
                </div>
                <div class="strategy-box status-gray">
                    <h4>Taker ${preview.taker.side}</h4>
                    <div class="strategy-detail">배팅 금액: $${preview.taker.investment.toFixed(2)} (${(preview.taker.price*100).toFixed(1)}%)</div>
                    <div class="strategy-detail">✓ ${preview.taker.side} 적중시: +$${preview.taker.profit_if_win.toFixed(2)} 수익</div>
                </div>
                <div class="strategy-box status-gray">
                    <h4>■ 총 투자금액</h4>
                    <div class="strategy-row"><span>$${preview.total_investment.toFixed(2)}</span></div>
                </div>
                <div class="strategy-box status-pink">
                    <h4>확정 손실</h4>
                    <div class="strategy-row highlight" style="color: ${lossColor}">-$${preview.guaranteed_loss.toFixed(2)} (-${lossRate.toFixed(2)}%)</div>
                </div>
                <div class="strategy-box status-yellow">
                    <h4>💡 어느 결과가 나와도</h4>
                    <div class="outcome-summary">
                        <div class="strategy-row">총 받는 금액: <span class="highlight">$${preview.outcome_summary.total_received.toFixed(2)}</span></div>
                        <div class="strategy-row">총 투자금액: <span>$${preview.total_investment.toFixed(2)}</span></div>
                        <div class="strategy-row">순손실: <span class="highlight">$${preview.outcome_summary.net_loss.toFixed(2)}</span></div>
                    </div>
                </div>
            `;
        } else if (preview.status === 'waiting' || preview.status === 'no_orderbook') {
            container.innerHTML = `
                <div class="strategy-box status-pink">
                    <h4>⏳ ${preview.status_message}</h4>
                </div>
            `;
        } else {
            container.style.display = 'none';
        }
    }
    
    hideStrategyPreview() {
        const container = document.getElementById('strategyPreview');
        if (container) {
            container.style.display = 'none';
        }
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
        this.hideStrategyPreview();
    }
    
    renderAccounts() {
        const list = document.getElementById('accountsList');
        
        if (this.accounts.length === 0) {
            list.innerHTML = '<p class="empty-state">계정이 없습니다</p>';
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
            const response = await fetch('/api/trade/execute', {
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
                const response = await fetch('/api/auto/start', {
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
                const response = await fetch('/api/auto/stop', {
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
            const response = await fetch('/api/auto/stats');
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
