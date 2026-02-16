# 오봇을 경봇과 별도 레포지토리로 분리하기

오봇(Opinion)과 경봇(Predict/Gyeong)을 **서로 다른 Git 저장소**로 나누는 방법을 정리했습니다.

---

## 1. 현재 구조 (한 레포에 둘 다 있음)

- **경봇**: Predict.fun 자동 거래 (`/gyeong`, `core/account.py`, `core/trader.py`, `core/auto_trader.py` 등)
- **오봇**: Opinion.trade 다중 로그인·자전 (`/`, `core/opinion_*.py`, `templates/opinion.html` 등)
- **공유**: `app.py` 하나가 두 대시보드·API를 모두 제공

---

## 2. 분리 후 목표 구조

| 레포지토리 | 내용 |
|------------|------|
| **gyeong-bot** (경봇) | Predict 전용: `/` → 경봇 대시, 경봇 API만 유지 |
| **o-bot** (오봇, 새 레포) | Opinion 전용: `/` → 오봇 대시, 오봇 API만 유지 |

---

## 3. 오봇 전용 레포(o-bot) 만들기

### 3-1. 새 저장소 생성

- GitHub/GitLab 등에서 **새 레포** 생성 (예: `o-bot`, `opinion-bot`)
- 로컬에 클론할 폴더 예: `~/Downloads/o-bot`

### 3-2. 오봇 전용으로 쓸 파일 목록

아래는 **gyeong-bot에서 복사해 오봇 레포로 옮길 파일**입니다. (경로는 새 레포 기준)

**앱·설정**

- `app.py` → **오봇 전용으로 수정** (경봇 라우트·import 제거, 아래 3-3 참고)
- `config.py` → Flask·기본 설정만 두거나, 오봇용 최소 설정
- `requirements.txt`
- `.env.example` (OPINION_*, PROXY 등만)
- `data/` (비어 있어도 됨, opinion_accounts.json 저장용)

**core (오봇이 쓰는 것만)**

- `core/opinion_config.py`
- `core/opinion_client.py`
- `core/opinion_account.py`
- `core/opinion_btc_topic.py`
- `core/opinion_manual_trade.py`
- `core/opinion_auto_trader.py`
- `core/opinion_errors.py`
- `core/opinion_clob_order.py`
- `core/btc_price.py` (오봇 수동/자동 거래에서 사용)
- `core/okx_balance.py` (Overall USDT 총합에서 사용)
- `core/__init__.py` (필요 시 비워 두거나 최소 유지)

**프론트**

- `templates/opinion.html`
- `templates/login.html`
- `static/js/opinion.js`
- `static/css/style.css` (오봇 페이지에서 쓰는 부분만 있어도 됨)
- `static/images/` (페페 등 오봇용 이미지)

**문서·규칙 (선택)**

- `오봇/.cursorrules` → 새 레포 루트의 `.cursorrules`로
- `docs/OPINION_*.md`, `docs/PROMPT_*.md` 등 오봇 관련 문서만

### 3-3. 오봇 전용 app.py로 정리할 내용

- **삭제할 것**: `from core.account import account_manager`, `core.market`, `core.trader`, `core.auto_trader`, `core.telegram_bot`, `core.validator`, `trader_module` 등 **경봇 전용** import·초기화
- **삭제할 라우트**: `@app.route('/gyeong')`, `/api/status`, `/api/accounts`, `/api/auto/*`, `/api/market/*` 등 **경봇 전용** 라우트
- **유지**: `/`, `/login`, `/api/opinion/*`, Opinion 관련 블록만 남기기

(필요하면 “오봇 전용 app.py 예시”를 별도 파일로 만들어 드릴 수 있습니다.)

---

## 4. 경봇 레포(gyeong-bot)에서 오봇 코드 제거

오봇을 새 레포로 뺀 뒤, **기존 gyeong-bot**에서는:

- **삭제**: `core/opinion_*.py`, `core/okx_balance.py`(경봇이 안 쓰면), `templates/opinion.html`, `static/js/opinion.js`, `오봇/` 폴더
- **app.py 수정**: Opinion import·라우트 전부 제거, `@app.route('/')` 를 경봇 대시(`index.html`)로 변경
- **정리**: `core/btc_price.py`는 경봇이 쓰면 유지, 오봇만 쓰면 제거

---

## 5. 작업 순서 제안

1. **오봇 새 레포** 생성 후, 위 3-2 목록대로 파일 복사
2. 새 레포에서 **app.py를 오봇 전용**으로 수정 (3-3)
3. 새 레포에서 `pip install -r requirements.txt`, `.env` 설정 후 실행해 보기
4. 문제 없으면 **gyeong-bot**에서 오봇 관련 코드/폴더 제거 (4번)
5. 두 레포 각각 커밋·푸시

---

## 6. 한 줄 요약

- **오봇** = 새 레포에 **오봇 전용 파일만** 복사하고, **app.py는 Opinion만** 남긴 뒤 독립 실행.
- **경봇** = 기존 gyeong-bot에서 **Opinion 관련 코드·폴더만** 지우면 별도 레포로 구분 완료.

원하면 “오봇 전용 app.py 초안”이나 “복사용 셸 스크립트”도 이어서 만들어 드리겠습니다.
