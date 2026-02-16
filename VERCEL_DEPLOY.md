# Vercel 배포 가이드 (오봇 O-Bot)

오봇(Opinion 전용)을 Vercel에 배포하는 방법입니다.

---

## Vercel에서 동작하는 것

| 기능 | 로컬 | Vercel |
|------|------|--------|
| 접속 암호 로그인 | ✅ | ✅ |
| Opinion 대시보드 (다중 로그인) | ✅ | ✅ |
| API (마켓, 수동 거래, BTC 갭 등) | ✅ | ✅ |
| **자동 거래 (Auto)** | ✅ | ❌ 유지 안 됨 |
| **BTC 실시간 스트림** | ✅ | REST fallback만 (첫 요청 시 지연 가능) |

자동 거래는 24시간 켜진 프로세스가 필요하므로, Vercel처럼 요청 시에만 실행되는 환경에서는 **수동 거래·대시보드**만 사용하는 것이 좋습니다. Auto가 필요하면 Railway, Render, Fly.io 등에서 실행하세요.

---

## 배포 방법

### 1. GitHub에 올리기

```bash
cd /Users/han/Downloads/gyeong-bot
git add .
git commit -m "오봇 전용 정리 및 배포 설정"
git push origin main
```

### 2. Vercel에 연결

1. [vercel.com](https://vercel.com) 로그인
2. [vercel.com/new](https://vercel.com/new) → **Import Git Repository**
3. **Hanvenue/O-Bot** 저장소 선택 후 Import

### 3. 환경 변수 설정 (필수)

Vercel 대시보드 → 프로젝트 선택 → **Settings** → **Environment Variables**

로컬 `.env`에 있는 **Opinion 용** 값을 그대로 넣으면 됩니다.

| 변수명 | 설명 |
|--------|------|
| `OPINION_API_KEY` | Opinion.trade API 키 (필수) |
| `OPINION_PROXY` | 프록시 `IP:PORT:USER:PASS` (필수) |
| `SECRET_KEY` | Flask 세션용 (예: 긴 랜덤 문자열) |
| `PYTH_API_URL` | (선택) 기본값 사용 가능 |
| `BTC_PRICE_FEED_ID` | (선택) 기본값 사용 가능 |
| `MIN_PRICE_GAP` | (선택) 기본 200 |
| `TIME_BEFORE_END` | (선택) 기본 300 |

`.env`를 그대로 복사해서 쓰셨다면, 위 항목만 Vercel에 동일하게 입력하면 됩니다.

### 4. 배포

**Save** 후 **Deployments** 탭에서 자동 배포되거나, **Redeploy**로 다시 배포할 수 있습니다.

---

## 배포 후 확인

- `https://프로젝트명.vercel.app` → 접속 암호 입력 후 Opinion 대시
- `/login` → 로그인 페이지
- `/api/opinion/proxy-status` → 프록시 설정 여부
- `/api/opinion/btc-price-gap` → BTC 시세·갭 (API 키·프록시 필요)

---

## 문제 해결

- **빌드 실패**: Vercel 빌드 로그에서 에러 확인. `requirements.txt` 의존성 확인.
- **500 에러**: 환경 변수(`OPINION_API_KEY`, `OPINION_PROXY`, `SECRET_KEY`)가 설정되었는지 확인.
- **첫 요청 느림**: 서버리스 콜드 스타트로 5–10초 걸릴 수 있음.
