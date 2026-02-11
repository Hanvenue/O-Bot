# Opinion.trade 다중 로그인

OKX Wallet PK로 **하나씩** 로그인하고, API 리턴값(포지션·거래 내역)을 UI에 표시하는 대시보드입니다.

## .env에 넣을 값

- **OPINION_PROXY**: `IP:PORT:USER:PASS` 형식 (없으면 UI에 「프록시를 추가해 주세요」 알림)
- **OPINION_API_KEY**: Opinion API 키 (OKX wallet과 세트로 발급된 키)
- **OPINION_DEFAULT_EOA**: 디폴트 계정 지갑 주소 (이 주소와 매칭되는 계정에서만 위 API 키 사용)

`.env.example`을 복사해 `.env`를 만든 뒤 위 값들을 채우면 됩니다.

## 로그인 흐름

1. 접속 암호 입력 후 메인 페이지 진입 (기존 경봇과 동일).
2. 메인은 **Opinion 다중 로그인** 화면.
3. **+ 계정 로그인 (PK 입력)** → 모달에서 OKX Wallet Private Key 입력.
4. 서버에서 PK → EOA 계산 후, Opinion API로 `positions/user/{EOA}`, `trade/user/{EOA}` 호출.
5. 성공 시 **API 리턴값 전부**를 화면에 표시 (Positions / Trades 접기·펼치기).
6. API 키는 디폴트 EOA와 같은 지갑일 때만 사용하도록 매칭.

## 로컬 실행

**Opinion만 쓸 때** (Predict 설정 없이):

```bash
cd /Users/han/.cursor/worktrees/__/ojg
export OPINION_ONLY=1
export SECRET_KEY=your-secret-key
python3 app.py
```

브라우저: `http://localhost:5001` → 접속 암호 입력 후 Opinion 대시보드.

**경봇(Predict)도 함께 쓸 때**  
기존처럼 `.env`에 `PREDICT_API_KEY`, `PROXY_1` 등 설정 후 `python3 app.py` (OPINION_ONLY 없이).

- `/` → Opinion 다중 로그인
- `/gyeong` → 기존 경봇 대시보드

## 배포 (새 레포지토리 + 배포)

1. **새 깃 레포지토리 만들기**  
   GitHub에서 새 repo 생성 후, 이 프로젝트를 푸시할 폴더에서:

   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/opinion-dashboard.git
   git add .
   git commit -m "Opinion 다중 로그인 UI"
   git push -u origin main
   ```

2. **Vercel 배포**  
   이미 `vercel.json`이 있으면, Vercel 대시보드에서 해당 repo 연결 후 배포.  
   환경 변수에 `OPINION_ONLY=1`, `SECRET_KEY=...` 설정.

3. **다른 호스팅**  
   `gunicorn` 등으로 `app:app` 실행하고, 환경 변수만 동일하게 설정하면 됨.

## 오봇 API 엔드포인트 (Opinion OpenAPI 연동)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/opinion/proxy-status` | 프록시 설정 여부 |
| GET | `/api/opinion/accounts` | 등록된 Opinion 계정 목록 |
| POST | `/api/opinion/login` | OKX Wallet PK 로그인 (Body: `private_key`) |
| GET | `/api/opinion/markets` | 시장 목록 (Query: `status`, `sortBy`, `page`, `limit`) |
| GET | `/api/opinion/market/<market_id>` | 시장 상세 |
| GET | `/api/opinion/token/latest-price` | 토큰 최신 가격 (Query: `token_id`) |
| GET | `/api/opinion/token/orderbook` | 토큰 호가창 (Query: `token_id`) |
| GET | `/api/opinion/token/price-history` | 가격 히스토리 (Query: `token_id`, `interval`) |
| GET | `/api/opinion/quote-tokens` | 거래 통화 목록 |
| GET | `/api/opinion/positions/<wallet_address>` | 지갑 포지션 (Query: `page`, `limit`) |
| GET | `/api/opinion/trades/<wallet_address>` | 지갑 거래 내역 (Query: `page`, `limit`) |

메인 UI(오봇)에서 시장 목록·거래 통화·시장 상세·호가·가격 조회 버튼으로 위 API를 호출해 결과를 볼 수 있습니다.

## 파일 구조

| 파일 | 설명 |
|------|------|
| `core/opinion_config.py` | .env에서 프록시·API키·디폴트 EOA 로드 |
| `core/opinion_client.py` | Opinion OpenAPI 호출 (시장/토큰/호가/포지션/거래/quoteToken) |
| `core/opinion_account.py` | 계정 관리 (디폴트 + PK 로그인, EOA-API키 매칭) |
| `templates/opinion.html` | Opinion 다중 로그인 + 시장/통화/조회 UI |
| `static/js/opinion.js` | 계정 목록·모달·API 결과·엔드포인트 호출 |

API 키·프록시·디폴트 EOA는 `.env`에 넣어서 보관합니다.
