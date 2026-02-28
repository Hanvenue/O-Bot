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

## 운영 시 자주 쓰는 명령어

매번 찾지 않도록 여기 적어 둡니다. (서버 IP·키 경로 바뀌면 여기만 수정)

| 할 일 | 명령어 |
|--------|--------|
| **서버 SSH 접속** | `ssh -i ~/Downloads/LightsailDefaultKey-eu-central-1.pem ubuntu@18.198.188.126` |
| **앱 재시작 (서버)** | `sudo systemctl restart obot` |
| **앱 로그 보기 (서버)** | `sudo journalctl -u obot -f` |
| **로컬 실행** | `cd /Users/han/Downloads/O-Bot && source venv/bin/activate && python3 app.py` |
| **로컬 재시작** | 터미널에서 `Ctrl+C` 후 위 로컬 실행 명령 다시 |

> 키/IP 변경 시: `docs/LIGHTSAIL_DEPLOY.md`와 이 표만 맞춰 두면 됨.

---

## 배포 (Vercel)

1. 이 저장소를 Vercel에 연결: [vercel.com/new](https://vercel.com/new) → **Import** → **Hanvenue/O-Bot**
2. **Environment Variables**에 로컬 `.env` 값 그대로 입력 (또는 [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md) 참고)
3. 배포 후 `https://프로젝트명.vercel.app` 에서 접속

자세한 단계는 [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md) 참고.

---

## 문서

- [docs/CODEBASE_REPORT.md](docs/CODEBASE_REPORT.md) – **전체 코드 분석** (구조·API·데이터 흐름·리스크)
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
