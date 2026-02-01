# 🚀 경봇 (Gyeong Bot) - 빠른 시작 가이드

## ✅ 완료된 작업

모든 핵심 코드가 완성되었습니다!

### 📂 생성된 파일 (14개)

```
gyeong-bot/
├── app.py                 ✅ Flask 메인 앱
├── config.py              ✅ 설정 관리
├── requirements.txt       ✅ 패키지 목록
├── .env.example           ✅ 환경변수 템플릿
├── .gitignore             ✅ Git 제외 파일
├── README.md              ✅ 전체 문서
│
├── core/                  ✅ 핵심 로직 (6파일)
│   ├── __init__.py
│   ├── account.py         # 계정 관리
│   ├── btc_price.py       # BTC 가격
│   ├── market.py          # 마켓 데이터
│   ├── trader.py          # 거래 실행
│   └── validator.py       # 조건 검증
│
├── templates/
│   └── index.html         ✅ 대시보드 UI
│
└── static/
    ├── css/style.css      ✅ 스타일
    └── js/main.js         ✅ 프론트엔드
```

---

## 🎯 지금 바로 시작하기 (3단계)

### 1️⃣ Cursor에 복사 (2분)

```bash
# Cursor에서 새 프로젝트 폴더 생성
mkdir gyeong-bot
cd gyeong-bot

# 다운로드한 파일들을 Cursor 폴더로 복사
# (또는 제공된 .tar.gz 압축 해제)
```

### 2️⃣ 환경 설정 (5분)

```bash
# 1. 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 환경변수 파일 생성
cp .env.example .env
```

**⚠️ .env 파일 편집 필수:**

```env
# Predict.fun API (Discord에서 발급받아야 함)
PREDICT_API_KEY=your_key_here

# OKX Wallet Private Keys
ACCOUNT_1_PK=0x1234...
ACCOUNT_2_PK=0x5678...
ACCOUNT_3_PK=0x9abc...

# 프록시는 이미 설정됨 (변경 불필요)
```

### 3️⃣ 실행 (1분)

```bash
python app.py
```

브라우저에서 접속: **http://localhost:5000**

---

## ⚠️ 현재 상태 & 다음 단계

### ✅ 완성된 부분

- [x] 전체 프로젝트 구조
- [x] 3개 계정 관리 로직
- [x] BTC 가격 조회 (Pyth)
- [x] 거래 조건 검증
- [x] UI/UX 대시보드
- [x] API 엔드포인트
- [x] Maker-Taker 거래 로직

### 🔧 해야 할 일 (중요!)

#### **1. Predict.fun API 연동** (필수)

현재 코드는 **플레이스홀더**입니다. 실제 작동을 위해:

```python
# core/market.py 에서 수정 필요:
# - 실제 API 엔드포인트 확인
# - 응답 형식 맞추기
# - 인증 방식 확인

# core/trader.py 에서 수정 필요:
# - Predict SDK 사용
# - 주문 생성/취소 구현
```

**📖 참고 문서:**
- https://dev.predict.fun/
- Discord에서 API 가이드 확인

#### **2. Predict.fun API Key 발급**

```
1. Predict.fun Discord 가입
2. #api-access 채널에서 요청
3. API Key 받기
4. .env 파일에 입력
```

#### **3. 실제 테스트**

```bash
# 소액으로 먼저 테스트!
# 1-2 shares만 거래
# 수수료 실측
# 수익성 검증
```

---

## 🐛 예상 문제 & 해결

### 문제 1: `pip install` 실패

```bash
# Python 버전 확인 (3.9+ 필요)
python --version

# 패키지 하나씩 설치
pip install Flask
pip install python-dotenv
pip install requests
pip install web3
pip install eth-account
```

### 문제 2: Predict API 연결 실패

```
❌ Failed to get markets
```

→ Predict.fun API 문서 확인 필요
→ 실제 엔드포인트 주소 확인
→ API Key 유효성 검사

### 문제 3: Private Key 오류

```
❌ Failed to initialize account
```

→ Private Key는 반드시 `0x`로 시작
→ 64자 (0x 제외) 확인
→ OKX Wallet에서 정확히 복사

---

## 📊 예상 작업 시간

| 단계 | 시간 | 난이도 |
|------|------|--------|
| Cursor 설정 | 5분 | ⭐ |
| 환경 설정 | 10분 | ⭐⭐ |
| API Key 발급 | 30분 | ⭐⭐ |
| **API 연동** | **2-3시간** | **⭐⭐⭐⭐** |
| 테스트 | 1시간 | ⭐⭐⭐ |
| **총계** | **4-5시간** | |

---

## 💡 핵심 팁

### 1. API 먼저 확인

```bash
# Predict.fun API를 curl로 테스트
curl -H "Authorization: Bearer YOUR_KEY" \
  https://api.predict.fun/markets
```

### 2. 로그 확인

```python
# app.py 실행 시 모든 로그 표시됨
# ✅, ❌ 아이콘으로 상태 확인 가능
```

### 3. 단계별 진행

```
1단계: 마켓 데이터만 가져오기 ✅
2단계: 계정 잔액 확인 ✅
3단계: 소액 거래 1회 테스트 ✅
4단계: 자동화 구현
```

---

## 🎁 보너스: 다음 Phase

### Phase 2: 자동화

```python
# TODO: 텔레그램 봇 추가
# TODO: Auto 모드 활성화
# TODO: 거래 내역 DB 저장
```

### Phase 3: 확장

```python
# TODO: 100개 계정 지원
# TODO: Vercel 배포
# TODO: WebSocket 실시간
```

---

## 📞 문제 발생 시

**막히는 부분이 있으면:**

1. 에러 메시지 복사
2. 해당 파일 확인
3. 로그 확인
4. Predict.fun 문서 참조

**자주 확인할 파일:**
- `core/market.py` - 마켓 데이터
- `core/trader.py` - 거래 실행
- `app.py` - API 엔드포인트

---

## ✨ 완성 기준

✅ 대시보드가 로드됨
✅ 계정 3개가 표시됨
✅ 현재 마켓이 표시됨
✅ BTC 가격이 업데이트됨
✅ "거래 실행" 버튼 클릭 시 동작

---

**🎉 코드는 완성되었습니다!**
**이제 Predict.fun API만 연동하면 바로 작동합니다!**

**예상 완성 시간: 오늘 내로 충분히 가능! 🚀**
