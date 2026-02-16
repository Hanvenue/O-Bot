# 오봇 (O-Bot)

**Opinion.trade** 다중 로그인 대시보드 + 수동/자동 거래 (BTC Up or Down 1시간 마켓)

이 레포는 **오봇 전용**입니다. 경봇(Predict.fun) 코드는 포함되어 있지 않습니다.

---

## 빠른 시작

### 1. 환경 설정

```bash
git clone https://github.com/Hanvenue/O-Bot.git
cd O-Bot
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경 변수

로컬에 이미 **Opinion.trade 용 API 키**를 `.env`에 저장해 두셨다면, 그 파일을 프로젝트 루트에 그대로 복사하면 됩니다.

없다면:

```bash
cp .env.example .env
# .env 편집: OPINION_API_KEY, OPINION_PROXY, SECRET_KEY 등
```

**필수**: `OPINION_API_KEY`, `OPINION_PROXY`, `SECRET_KEY`

### 3. 실행

```bash
python3 app.py
```

브라우저: `http://localhost:5001` → 접속 암호 입력 후 Opinion 대시보드.

---

## 배포 (Vercel)

1. 이 저장소를 Vercel에 연결: [vercel.com/new](https://vercel.com/new) → **Import** → **Hanvenue/O-Bot**
2. **Environment Variables**에 로컬 `.env` 값 그대로 입력 (또는 [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md) 참고)
3. 배포 후 `https://프로젝트명.vercel.app` 에서 접속

자세한 단계는 [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md) 참고.

---

## 문서

- [OPINION_README.md](OPINION_README.md) – Opinion 다중 로그인·API 설명
- [QUICKSTART.md](QUICKSTART.md) – 빠른 시작 (해당 시 사용)
- [AUTO_MODE_GUIDE.md](AUTO_MODE_GUIDE.md) – 자동 거래 (로컬/상시 호스팅 권장)

---

## 프로젝트 구조 (오봇)

```
O-Bot/
├── app.py              # Flask 앱 (Opinion 전용)
├── config.py           # 설정
├── core/
│   ├── btc_price.py    # Pyth BTC 시세
│   ├── opinion_*.py    # Opinion API·계정·수동/자동 거래
│   ├── okx_balance.py  # USDT 잔액 (선택)
│   └── ...
├── templates/          # opinion.html, login.html
├── static/             # opinion.js, style.css
└── .env                # 직접 생성 (또는 .env.example 복사)
```
