# 🤖 경봇 (Gyeong Bot)

Predict.fun BTC/USD 15분 자동거래 봇

## 📋 프로젝트 개요

**목적**: Predict.fun 15분 BTC/USD 마켓에서 자전거래(Wash Trading) 실행
**전략**: Maker(수수료 0%) + Taker 조합으로 손익 0 이상 유지, 리워드로 수익

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 1. 프로젝트 클론/복사
cd gyeong-bot

# 2. 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 패키지 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
# .env.example 을 .env 로 복사
cp .env.example .env

# .env 파일 편집
nano .env
```

**필수 설정**:
```env
# Predict.fun API Key (Discord에서 발급)
PREDICT_API_KEY=your_api_key_here

# OKX Wallet Private Keys (3개 계정)
ACCOUNT_1_PK=0x...
ACCOUNT_2_PK=0x...
ACCOUNT_3_PK=0x...

# 프록시 (제공된 3개)
PROXY_1=64.137.95.154:6637:lzojpoeh:7c72o6xe57wp
PROXY_2=104.250.207.162:6560:lzojpoeh:7c72o6xe57wp
PROXY_3=171.22.250.250:6369:lzojpoeh:7c72o6xe57wp
```

### 3. 실행

```bash
python app.py
```

브라우저에서 접속: `http://localhost:5000`

## 📁 프로젝트 구조

```
gyeong-bot/
├── app.py                 # Flask 메인 애플리케이션
├── config.py              # 설정 관리
├── requirements.txt       # Python 패키지
├── .env                   # 환경변수 (직접 생성)
├── .env.example           # 환경변수 템플릿
│
├── core/                  # 핵심 비즈니스 로직
│   ├── __init__.py
│   ├── account.py         # 계정 관리 (3개 OKX Wallet)
│   ├── market.py          # Predict.fun 마켓 데이터
│   ├── btc_price.py       # Pyth Network BTC 가격
│   ├── validator.py       # 거래 조건 검증
│   └── trader.py          # 거래 실행 (Maker-Taker)
│
├── templates/             # HTML 템플릿
│   └── index.html         # 메인 대시보드
│
├── static/                # 정적 파일
│   ├── css/
│   │   └── style.css      # 스타일시트
│   └── js/
│       └── main.js        # 프론트엔드 로직
│
└── utils/                 # 유틸리티 (예정)
    └── logger.py
```

## 🎯 핵심 기능

### ✅ Phase 1 (완료!)

- [x] 3개 계정 관리 (OKX Wallet + 프록시)
- [x] BTC 실시간 가격 조회 (Pyth Network)
- [x] 15분 마켓 필터링
- [x] 거래 조건 검증 ($200 갭)
- [x] 수동 거래 실행 (CTA 버튼)
- [x] 기본 대시보드 UI
- [ ] **실제 Predict.fun API 연동** (TODO)

### ✅ Phase 2 (완료!)

- [x] **Auto 모드 (자동 거래)** 🔥
- [x] **텔레그램 봇 (알림 + 킬스위치)** 🔥
- [x] 거래 통계 추적
- [x] 승률 계산
- [ ] WebSocket 실시간 오더북 (선택사항)

### 🚀 Phase 3 (향후)

- [ ] 100개 계정 확장
- [ ] Vercel 배포
- [ ] 수익 자동 회수
- [ ] 대시보드 개선
- [ ] 백테스팅 시스템

## 🔧 주요 설정

### config.py

```python
MIN_PRICE_GAP = 200        # 최소 가격 갭 ($200)
MIN_BALANCE = 20           # 최소 잔액 ($20)
TIME_BEFORE_END = 300      # 진입 시간 (5분 = 300초)
```

## 📡 API 엔드포인트

### GET /api/status
시스템 상태 및 계정 정보

**Response:**
```json
{
  "success": true,
  "accounts": [...],
  "total_accounts": 3,
  "total_balance": 60.50
}
```

### GET /api/market/current
현재 활성 마켓 정보

**Response:**
```json
{
  "success": true,
  "market": {
    "id": 12345,
    "title": "BTC/USD Up/Down 15min",
    "start_price": 98000,
    "current_btc_price": 98250,
    "price_gap": 250,
    "trade_ready": true,
    "trade_direction": "UP",
    "time_remaining": 120
  }
}
```

### POST /api/trade/execute
거래 실행

**Request:**
```json
{
  "market_id": 12345,
  "shares": 10,
  "direction": "UP"
}
```

**Response:**
```json
{
  "success": true,
  "maker_order": "0x...",
  "taker_order": "0x...",
  "direction": "UP",
  "price": 0.88,
  "shares": 10
}
```

### POST /api/auto/start
Auto 모드 시작

**Request:**
```json
{
  "shares": 10
}
```

**Response:**
```json
{
  "success": true,
  "message": "Auto mode started with 10 shares"
}
```

### POST /api/auto/stop
Auto 모드 중지

**Response:**
```json
{
  "success": true,
  "message": "Auto mode stopped"
}
```

### GET /api/auto/stats
Auto 모드 통계

**Response:**
```json
{
  "success": true,
  "stats": {
    "is_running": true,
    "auto_mode_enabled": true,
    "total_trades": 15,
    "successful_trades": 14,
    "failed_trades": 1,
    "success_rate": 93.3,
    "total_profit": 0.12,
    "shares_per_trade": 10
  }
}
```

## ⚠️ 중요 사항

### 1. Predict.fun API 연동 필요

현재 코드는 **플레이스홀더**입니다. 실제로 작동하려면:

```bash
# 1. Predict.fun Discord 가입
# 2. API Key 발급 요청
# 3. SDK 문서 확인: https://dev.predict.fun/
```

**TODO 항목**:
- `core/market.py`: 실제 API 엔드포인트 구현
- `core/trader.py`: Predict SDK로 주문 실행
- `core/account.py`: 로그인 및 인증

### 2. 프록시 제약

현재 프록시 3개로 3개 계정만 운영 가능합니다.
- 계정 확장 시 추가 프록시 구매 필요
- 1 계정 : 1 프록시 (필수)

### 3. 법적 리스크

**자전거래(Wash Trading)는 불법입니다.**
- 한국 자본시장법 위반
- Predict.fun ToS 위반 가능
- 변호사 상담 필수

## 🐛 디버깅

### 로그 확인

```bash
# Flask 로그 (터미널)
# 모든 요청/응답이 표시됩니다
```

### 문제 해결

**1. API 연결 실패**
```
❌ Failed to get markets: Connection error
```
→ PREDICT_API_KEY 확인
→ 인터넷 연결 확인

**2. 계정 로그인 실패**
```
❌ Failed to initialize account
```
→ Private Key 형식 확인 (0x로 시작)
→ 프록시 연결 테스트

**3. BTC 가격 조회 실패**
```
❌ Failed to get BTC price from Pyth
```
→ Pyth Network API 상태 확인
→ https://hermes.pyth.network/api/latest_price_feeds 테스트

## 📚 참고 자료

### 프로젝트 문서
- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작 가이드
- [AUTO_MODE_GUIDE.md](AUTO_MODE_GUIDE.md) - Auto 모드 사용법
- [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) - 텔레그램 봇 설정

### 외부 문서
- [Predict.fun API Docs](https://dev.predict.fun/)
- [Pyth Network](https://pyth.network/)
- [OKX Wallet](https://www.okx.com/web3)
- [Telegram Bot API](https://core.telegram.org/bots/api)

## 🤝 개발 진행

### 다음 단계

1. **Predict.fun API 연동**
   - Discord 가입
   - API Key 발급
   - 실제 마켓 데이터 테스트

2. **소액 테스트**
   - 1-2 shares로 실험
   - 수수료 실측
   - 수익성 검증

3. **Auto 모드 개발**
   - 텔레그램 봇 연동
   - 자동 실행 로직
   - 킬스위치

---

**만든이**: Chipmunk  
**목적**: Predict.fun 리워드 프로그램 활용  
**면책**: 법적 책임은 사용자에게 있음
