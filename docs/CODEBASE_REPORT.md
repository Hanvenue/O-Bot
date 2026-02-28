# O-Bot Codebase Report

Structured overview for developers and AI. Concise; use as a quick reference.

---

## 1. Project structure

| Path | Purpose |
|------|--------|
| **app.py** | Flask app entry: routes, session auth, WS startup, Opinion/CLOB/auto/manual APIs |
| **config.py** | Central config from `.env`: Pyth, BSC, trading params, proxy pool, Flask |
| **core/** | Opinion.trade logic, CLOB orders, BTC price, accounts, errors |
| **templates/** | `opinion.html` (main dashboard), `login.html` (password gate) |
| **static/** | `css/style.css`, `js/opinion.js` (UI + API calls) |
| **docs/** | PDCA snapshots, OPINION_*.md, COLLAB_WORKFLOW, deployment/QA docs |
| **utils/** | `logger.py` (logging helpers) |
| **scripts/** | `test_opinion_proxy.py`, `qa_api_response.py` (manual/QA) |
| **data/** | Runtime: `opinion_accounts.json` (persisted Opinion accounts) |
| **env.template / .env.example** | Env var templates; copy to `.env` and fill |

**Key files in core:**

- `opinion_config.py` — Loads `.env` Opinion keys/proxies; `get_proxy_dict`, `has_proxy`, `get_env_accounts`
- `opinion_account.py` — Multi-account manager; PK login, EOA derivation, persist to JSON
- `opinion_client.py` — REST client for Opinion OpenAPI (markets, orderbook, positions, trades)
- `opinion_clob_order.py` — CLOB SDK: limit/market orders, cancel, order status (BSC RPC + proxy)
- `opinion_manual_trade.py` — 1h market status + execute wash trade (Maker LIMIT + Taker MARKET/LIMIT)
- `opinion_auto_trader.py` — Background loop: 1h market check → `execute_manual_trade` when ready
- `opinion_ws_client.py` — Opinion WebSocket: orderbook depth.diff, best ask, full snapshot
- `opinion_btc_topic.py` — “Bitcoin Up or Down” topic/market resolution (5min cache)
- `btc_price.py` — Pyth Hermes WS + Benchmarks: current BTC price, price-at-timestamp
- `okx_balance.py` — USDT balance: OKX Web3 API or BSC RPC fallback
- `opinion_errors.py` — Map Opinion/HTTP codes to user-facing messages; `interpret_opinion_api_response`
- `opinion_geo.py` — Proxy IP → country/flag (ip-api.com, cached)

---

## 2. Entry point & config

**How the app starts**

- **Local:** `python app.py` → Flask dev server on `PORT` (default 5001), `host='0.0.0.0'`, `threaded=True`.
- **Production:** Typically **gunicorn** (or similar) runs `app:app`; comment in `app.py` refers to “gunicorn/flask” for WS startup. **Vercel:** `vercel.json` routes all requests to `app.py` (serverless Python).

**config.py**

- Loads `.env` from project root.
- **Opinion (O-Bot):** Not validated by `Config.validate()` in this repo (Predict/account checks removed).
- **Pyth:** `PYTH_API_URL`, `BTC_PRICE_FEED_ID` — REST + Hermes WS for BTC price.
- **Trading:** `MIN_PRICE_GAP`, `MIN_BALANCE`, `TIME_BEFORE_END`, `POST_MAKER_DELAY_SEC`, `WASH_TRADE_POLL_*`, `USE_TAKER_MARKET_ORDER`, `SKIP_BALANCE_CHECK`.
- **Flask:** `SECRET_KEY`, `FLASK_ENV`, `DEBUG`.
- **Legacy/Predict:** `PREDICT_*`, `ACCOUNTS`, `PROXY_POOL`, `TELEGRAM_*` (present but O-Bot uses Opinion-specific env).

**.env / env.template**

- **Opinion per-account:** `OPINION_EOA_N`, `OPINION_API_KEY_N`, `OPINION_PROXY_N` (N=1..20); N=1 also as `OPINION_DEFAULT_EOA`, `OPINION_API_KEY`, `OPINION_PROXY`.
- **CLOB:** `OPINION_CLOB_PK_N`, `OPINION_MULTISIG_N` (Gnosis Safe for BNB), `OPINION_CLOB_HOST`, `BSC_RPC_URL`.
- **Pyth:** `PYTH_API_URL`, `BTC_PRICE_FEED_ID`.
- **Trading:** `MIN_PRICE_GAP`, `TIME_BEFORE_END`, `SKIP_BALANCE_CHECK`, etc.
- **App:** `SECRET_KEY`, `FLASK_ENV`, `FLASK_DEBUG`, `PORT`.

---

## 3. Core logic (per module)

- **opinion_account** — Manages multiple Opinion “accounts” (EOA + api_key + proxy). PK login derives EOA, optional name; persists to `data/opinion_accounts.json`. Used by manual/auto trade (Maker/Taker selection) and by REST/CLOB (per-account key/proxy).
- **opinion_client** — Thin REST layer over Opinion OpenAPI (markets, market by id, orderbook, price history, quote tokens, positions, trades). All calls use (api_key, proxy). Used by btc_topic, manual_trade, app routes.
- **opinion_clob_order** — Builds CLOB client from `OpinionAccount` + `OPINION_CLOB_PK_N` / `OPINION_MULTISIG_N`; injects proxy into SDK. `place_limit_order`, `place_market_order`, `cancel_order`, `get_order_status`. Used only by `opinion_manual_trade` (and thus by auto_trader).
- **opinion_manual_trade** — `get_1h_market_for_trade`: resolves 1h BTC Up/Down market (via btc_topic), gets orderbook (REST or WS), computes Maker/Taker prices and strategy preview; returns `trade_ready`, `trade_direction`, `strategy_preview`. `execute_manual_trade`: validates accounts, then `_run_wash_trade_via_clob` (balance check → Maker LIMIT → short delay → Taker MARKET/LIMIT → poll/cancel). Uses btc_price (gap), opinion_account, opinion_clob_order, okx_balance, opinion_ws_client (orderbook).
- **opinion_auto_trader** — Singleton. `start()` spawns daemon thread that loops: `get_1h_market_for_trade(skip_time_check=False)` then `execute_manual_trade` when `trade_ready`. Tracks last_result, stats (success/fail), cooldown. Used by `/api/opinion/auto/*` routes.
- **opinion_ws_client** — Connects to Opinion WS (apikey in URL). Subscribes to `market.depth.diff` by market_id; maintains cumulative orderbook state; TTL-based REST fallback. Exposes `get_best_ask_from_ws`, `get_full_orderbook_snapshot`. Used by manual_trade (best ask) and app route for orderbook.
- **btc_price** — Pyth Hermes WebSocket for live BTC; Pyth Benchmarks for historical price at timestamp. Caches stream price and per-timestamp prices. Used by btc-price-gap route and manual_trade (gap/direction).
- **okx_balance** — USDT balance by address: OKX Web3 API if credentials set, else BSC RPC (USDT contract). Used by manual_trade (pre-trade balance check) and overall USDT route.
- **opinion_btc_topic** — Fetches activated markets, filters “Bitcoin Up or Down”, picks current (cutoff > now or latest past). 5min cache; cache invalidated when market ends. Returns topic_id and optionally full market dict. Used by btc-up-down, btc-price-gap, manual_trade.
- **opinion_errors** — `OPINION_API_CODE_MESSAGES`, `HTTP_STATUS_MESSAGES`, `AUTO_ERROR_CODES`. `interpret_opinion_api_response(status_code, body)` → `user_message` for UI. `get_auto_error_message(code)` for auto/manual error text. Used by app routes and CLOB error handling.

---

## 4. API surface (Flask routes)

| Method | Route | Description |
|--------|--------|-------------|
| GET/POST | `/login` | Password gate; POST sets session, redirects to index |
| POST | `/login/check` | JSON password check for API clients |
| GET | `/` | Serves `opinion.html` (dashboard) |
| GET | `/api/opinion/proxy-status` | `{ has_proxy }` for UI alert |
| GET | `/api/opinion/accounts` | List registered Opinion accounts |
| POST | `/api/opinion/login` | Login with OKX Wallet PK (and optional name); returns positions/trades etc. |
| GET | `/api/opinion/btc-up-down` | Latest Bitcoin Up or Down market (1h cache); full market payload |
| GET | `/api/opinion/btc-price-gap` | Start/current BTC price and gap for current 1h market (Pyth) |
| GET | `/api/opinion/manual-trade/status` | 1h market trade status and strategy preview (topic_id, shares query) |
| POST | `/api/opinion/manual-trade/execute` | Run manual wash trade (body: topic_id, account_id, shares, direction) |
| POST | `/api/opinion/auto/start` | Start auto trader (body: shares, optional account_id) |
| POST | `/api/opinion/auto/stop` | Stop auto trader |
| GET | `/api/opinion/auto/status` | Auto trader state (running, account_id, last_error) |
| GET | `/api/opinion/auto/error-message` | Last error message for UI |
| GET | `/api/opinion/auto/stats` | Success/fail counts, last_result |
| GET | `/api/opinion/overall` | Aggregate volume or USDT (query: metric=volume\|usdt, range=6h\|1d\|7d\|30d) |
| GET | `/api/opinion/markets` | Market list (status, sortBy, page, limit) |
| GET | `/api/opinion/market/<id>` | Single market detail |
| GET | `/api/opinion/token/latest-price` | Token latest price (token_id) |
| GET | `/api/opinion/token/orderbook` | Orderbook (token_id; optional market_id for WS snapshot) |
| GET | `/api/opinion/token/price-history` | Price history (token_id, interval) |
| GET | `/api/opinion/quote-tokens` | Quote tokens list |
| GET | `/api/opinion/positions/<wallet>` | Positions for wallet |
| GET | `/api/opinion/trades/<wallet>` | Trades for wallet |
| GET | `/api/btc/price` | Current BTC price (Pyth) |

---

## 5. Frontend

**templates/opinion.html**

- Single-page dashboard: header, proxy alert, account list, “계정 로그인” button.
- BTC price & gap card (주청 시간 기준), “불러오기” for 1h market, market card (topicId, title, start/end, volume).
- Shares: slider + number input (1–1000), Up/Down ratio, total cost, GAP → Maker.
- Buttons: “자동 Go!”, “자동 중지”, “수동 Go!”; manual trade result div; “직전 거래 성공 여부” (Pepe) card; Overall chart (volume/USDT, 6h/1d/7d/30d).
- Login modal: PK (and optional name) for Opinion login.

**static/js/opinion.js**

- **Login:** `openLoginModal` / `closeLoginModal`; `submitOpinionLogin` → POST `/api/opinion/login` → refresh accounts, show login result.
- **Load market:** “불러오기” → `loadBtcUpDown()` → GET `/api/opinion/btc-up-down` → `renderBtcUpDownCard(data)`; sets `window.currentOpinionTopicId`; triggers `updateSharesPriceDisplay()`.
- **Shares/status:** Slider/input sync; `updateSharesPriceDisplay()` calls `/api/opinion/manual-trade/status?topic_id&shares` and updates ratio, total, GAP text; stores `currentOpinionTradeDirection`, `currentOpinionGapUsd`, `currentOpinionMakerAccountId` for manual execute.
- **Manual Go:** `runManualGo()` → POST `/api/opinion/manual-trade/execute` with shares, topic_id, account_id, direction from globals → show success/error in `#manualTradeResult` and update “직전 거래” Pepe card.
- **Auto Go:** `runAutoGo()` → POST `/api/opinion/auto/start`; `runAutoStop()` → POST `/api/opinion/auto/stop`; `pollOpinionAutoStats()` → GET `/api/opinion/auto/stats` and toggle Go/Stop visibility + status text; updates last-trade Pepe from `last_result`.
- **Overall:** `loadOverallChart(metric, range)` → GET `/api/opinion/overall?metric=&range=`; Chart.js bar chart.
- **Auth:** `fetchWithAuth` uses `credentials: 'include'`; 401 → redirect to `/login`.
- Intervals: `updateBtcPriceGapCard` every 3s; `updateSharesPriceDisplay` every 5s; `loadBtcUpDown` every 1h; `pollOpinionAutoStats` every 5s.

---

## 6. Data flow

**“수동 Go!” flow (button → API → manual_trade → CLOB → response)**

1. User clicks “수동 Go!” → `runManualGo()` in `opinion.js`.
2. Body: `shares`, `topic_id` (= `window.currentOpinionTopicId`), `account_id` (= `currentOpinionMakerAccountId`), `direction` (= `currentOpinionTradeDirection`).
3. POST `/api/opinion/manual-trade/execute` → `opinion_manual_trade_execute()` in `app.py`.
4. `execute_manual_trade(topic_id, shares, direction, maker_account_id, …)` in `opinion_manual_trade.py`: calls `get_1h_market_for_trade(..., direction_override=...)` to get `trade_ready`, tokens, prices; picks Maker/Taker accounts; then `_run_wash_trade_via_clob(...)`.
5. `_run_wash_trade_via_clob`: balance check via `okx_balance`; `place_limit_order(maker_account, ...)` then after delay `place_market_order` (or limit) for taker; poll `get_order_status`; on timeout, `cancel_order`. Both orders go through `opinion_clob_order` (CLOB SDK + BSC + proxy).
6. Result dict (success, maker_order_id, taker_order_id, error, …) returned to app; app returns JSON to client.
7. `opinion.js` shows result in `#manualTradeResult` and updates “직전 거래” card.

**“1시간 마켓 불러오기” flow (button → btc-up-down → btc_topic cache → UI)**

1. User clicks “불러오기” → `loadBtcUpDown()` in `opinion.js`.
2. GET `/api/opinion/btc-up-down` → `opinion_btc_up_down()` in `app.py`.
3. `get_latest_bitcoin_up_down_market()` in `opinion_btc_topic.py`: if cache valid and market not ended, returns cached `(topic_id, market)`; else calls `get_markets(..., status=activated)` via `opinion_client`, filters “Bitcoin Up or Down”, picks current by cutoff, sets 5min cache and returns topic_id + market.
4. If market not in cache, app may call `get_market(topic_id, ...)` to fetch full market.
5. App returns `{ success, topicId, result: market }`.
6. `renderBtcUpDownCard(data)` updates DOM (topicId, title, start/end, volume, image), sets `window.currentOpinionTopicId`, calls `updateSharesPriceDisplay()` which hits `/api/opinion/manual-trade/status` to fill shares/GAP/preview.

---

## 7. Dependencies (external services)

| Service | Where used | Purpose |
|--------|------------|--------|
| **Opinion API** (REST) | `opinion_client`, `opinion_btc_topic`, account/trades/positions | Markets, orderbook, positions, trades; via proxy when set |
| **Opinion CLOB** (proxy.opinion.trade:8443) | `opinion_clob_order` | Place/cancel orders, order status (SDK uses proxy + BSC) |
| **Opinion WebSocket** (ws.opinion.trade) | `opinion_ws_client` | Real-time orderbook depth.diff |
| **Pyth (Hermes + Benchmarks)** | `btc_price` | Live BTC price; historical price at timestamp for gap |
| **BSC RPC** | `opinion_clob_order` (SDK), `okx_balance` (fallback) | Signing/tx; USDT balance when OKX not used |
| **OKX Web3 API** | `okx_balance` | USDT balance by address (optional; needs OKX_WEB3_* env) |
| **Proxy (per-account)** | All Opinion REST/CLOB and optional balance calls | IP:PORT or IP:PORT:USER:PASS in .env |
| **ip-api.com** | `opinion_geo` | Proxy IP → country/flag (45 req/min; cached) |

---

## 8. Risks & improvements

**Risks**

- **Secrets:** Access password in `app.py` is hardcoded (`ACCESS_PASSWORD`). `.env` holds API keys, PKs, proxy credentials; must not be committed.
- **Error handling:** Some routes return 500 with `str(e)`; Opinion non-400 errors are normalized via `opinion_errors.interpret_opinion_api_response` where used; ensure all Opinion/CLOB paths go through it for consistent user messages.
- **Rate limits:** Opinion (e.g. 15 req/s), ip-api.com (45/min), BSC public RPC limits; no central retry/backoff.
- **Concurrency:** Manual “수동 Go!” can be clicked repeatedly; UI disables button but no server-side idempotency for the same (topic, account, direction) in a short window.

**Dead / legacy**

- `config.py`: `PREDICT_*`, `ACCOUNTS`, `Config.validate()` are for Predict/경봇; O-Bot doesn’t call `validate()`.
- `requirements.txt`: `predict-sdk` listed but O-Bot is Opinion-only; safe to remove if no script uses it.

**Suggested improvements**

- **Logging:** Structured logging (e.g. request id, topic_id, account_id) for manual/auto trades and CLOB calls; rotate logs in production.
- **Tests:** No automated tests in repo; add at least smoke tests for critical routes and `get_1h_market_for_trade` / `execute_manual_trade` with mocks.
- **Docs:** Keep README/OPINION_*.md in sync with env vars and flows; this report can live in `docs/` and be updated on big changes.
- **Secrets:** Move access password to `.env`; use one strong `SECRET_KEY` in production.
- **Idempotency:** Optional short-lived “trade request” token or (topic_id, account_id, direction, ts_bucket) to reject duplicate manual executes within a few seconds.

---

*Generated for the O-Bot repository. Update this file when adding routes, core modules, or external services.*
