# Vercel 배포 가이드

경봇을 Vercel에 배포하는 방법입니다.

---

## ⚠️ 중요: Vercel에서 동작하지 않는 기능

Vercel은 **서버리스** 환경입니다.  
요청이 올 때만 잠깐 실행되고 바로 꺼집니다.

| 기능 | 로컬 | Vercel |
|------|------|--------|
| 대시보드 (웹 UI) | ✅ | ✅ |
| API (상태 조회, 수동 거래 등) | ✅ | ✅ |
| **Auto 모드 (자동 거래)** | ✅ | ❌ 작동 안 함 |
| **텔레그램 봇** | ✅ | ❌ 작동 안 함 |

**Auto 모드와 텔레그램 봇**은 계속 켜져 있어야 하는 프로세스라서, Vercel처럼 요청 시에만 실행되는 환경에서는 사용할 수 없습니다.

> 💡 Auto 모드 + 텔레그램이 필요하다면 **Railway**, **Render**, **Fly.io** 같은 24시간 켜져 있는 호스팅을 사용해야 합니다.

---

## 배포 방법

### 1. Vercel 계정 & CLI 설치

1. [vercel.com](https://vercel.com) 가입
2. Vercel CLI 설치 (선택):

```bash
npm i -g vercel
```

### 2. Git에 올리기

```bash
cd /Users/han/Downloads/gyeong-bot
git init
git add .
git commit -m "Initial commit"
# GitHub에 저장소 만들고 push
git remote add origin https://github.com/사용자명/gyeong-bot.git
git push -u origin main
```

### 3. Vercel에 배포

**방법 A: 웹에서 배포**

1. [vercel.com/new](https://vercel.com/new) 접속
2. "Import Git Repository"에서 위에서 만든 저장소 선택
3. **Environment Variables**에 아래 변수 입력 (필수)

**방법 B: CLI로 배포**

```bash
cd /Users/han/Downloads/gyeong-bot
vercel
```

처음 실행 시 로그인·프로젝트 설정 안내가 나옵니다.

### 4. 환경 변수 설정 (필수)

Vercel 대시보드 → 프로젝트 → **Settings** → **Environment Variables**에서 아래를 등록하세요.

**Predict.fun API (필수)**  
| 변수명 | 설명 |
|--------|------|
| `PREDICT_API_KEY` | Predict.fun API 키 (Discord에서 발급) |
| `PREDICT_BASE_URL` | `https://api.predict.fun` (기본값) |
| `ACCOUNT_1_PK` | 계정 1 프라이빗 키 |
| `ACCOUNT_2_PK` | 계정 2 프라이빗 키 |
| `ACCOUNT_3_PK` | 계정 3 프라이빗 키 |
| `PROXY_1` | 프록시 1 (IP:PORT:USER:PASS) |
| `PROXY_2` | 프록시 2 |
| `PROXY_3` | 프록시 3 |
| `PYTH_API_URL` | (선택) Pyth API URL |
| `BTC_PRICE_FEED_ID` | (선택) BTC 가격 피드 ID |

`.env.example`에 있는 값들을 Vercel 환경 변수에 그대로 넣으면 됩니다.

---

## 배포 후 확인

배포가 끝나면 `https://프로젝트명.vercel.app` 형태의 URL이 생깁니다.

- `/` → 대시보드
- `/api/status` → 계정 상태
- `/api/market/current` → 현재 마켓
- `/api/trade/execute` → 수동 거래 (POST)

---

## 문제 해결

**배포가 실패할 때**

- 터미널 또는 Vercel 로그에서 에러 메시지 확인
- `requirements.txt`에 있는 패키지가 모두 설치되는지 확인 (특히 `predict-sdk` 버전)
- 환경 변수가 Vercel에 제대로 들어갔는지 확인

**페이지가 안 열릴 때**

- 5–10초 정도 기다리기 (서버리스 콜드 스타트)
- 새로고침 후 다시 시도
