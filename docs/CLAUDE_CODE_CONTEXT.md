# Claude Code용 레포 맥락 (토큰 절약)

**리뷰/PR 전에 이 문서만 읽으면, 전체 코드베이스를 돌며 파악할 필요 없이 변동사항과 구조를 이해할 수 있습니다.**

---

## 1. 이 레포가 무엇인지 (한 줄)

- **O-Bot (오봇)** 전용 레포. **Opinion.trade** 다중 로그인·수동/자동 거래만 포함.

---

## 2. 최근 큰 변동 (한눈에)

| 변동 | 설명 |
|------|------|
| **레포 분리** | 원격 = `https://github.com/Hanvenue/O-Bot`. 모든 수정·푸시는 여기만 향함. |
| **app.py** | `/`, `/login`, `/api/opinion/*`, `/api/btc/price` 만 존재 (O-Bot 전용 라우트). |
| **core/** | `opinion_*.py`, `btc_price.py`, `okx_balance.py` 등 O-Bot용 모듈만 유지. |
| **templates/** | `opinion.html`, `login.html` 사용. |
| **static/** | `opinion.js`, `style.css`, `images/` 유지. |
| **폴더 구조** | **`오봇` 하위 폴더 제거.** 루트 = 프로젝트 전체. 규칙·문서는 루트 `.cursorrules`, 루트 `docs/` 에만 있음. |
| **설정** | `config.py`는 유지하되 오봇에서 `Config.validate()` 호출 안 함. `.env.example` 은 Opinion·Flask·Pyth 위주로 정리. |

---

## 3. 현재 구조 (리뷰 시 참고)

```
(루트 = 오봇 프로젝트 전체)
├── app.py              # Flask, Opinion 전용 라우트만
├── config.py
├── core/
│   ├── btc_price.py
│   ├── okx_balance.py
│   ├── opinion_*.py     # config, account, client, btc_topic, manual_trade, auto_trader, errors, clob_order
│   └── __init__.py
├── templates/          # opinion.html, login.html
├── static/             # js/opinion.js, css/style.css, images/
├── docs/               # 문서 + .pdca-snapshots 등
├── .cursorrules        # 오봇 프로젝트 규칙
└── (기타) README.md, VERCEL_DEPLOY.md, .env.example 등
```

---

## 4. Claude Code 리뷰 시 (토큰 절약)

- **전체 코드 리뷰는 하지 말 것.** 이 문서로 구조·변동을 이미 이해한 상태로 간주.
- **해당 브랜치의 `git diff`(또는 사용자가 지정한 변경 파일)만** 보고 리뷰·PR 작성.
- 추가로 꼭 볼 것: `docs/COLLAB_WORKFLOW.md` (역할 분담·브랜치 규칙).
- 에러 처리·Opinion API 관련은 `core/opinion_errors.py`, `docs/OPINION_ERROR_HANDLING.md` 참고 가능.

---

## 5. 사용자에게 전달할 프롬프트 (복사용)

Claude Code를 열고 리뷰/PR을 맡길 때 아래를 붙여넣으면 됩니다.

```
이 레포는 오봇(O-Bot) 전용이야. 변동사항·구조는 전체 코드 돌지 말고 docs/CLAUDE_CODE_CONTEXT.md 만 읽고 이해한 다음, [이 브랜치 / 이 PR] 의 diff만 보고 리뷰(또는 PR 설명) 해 줘. 토큰 아끼려고 전체 리뷰은 하지 마.
```

브랜치/PR을 지정할 때는 `[이 브랜치 / 이 PR]` 부분을 예: `main과 feat/xxx 의 diff` 처럼 구체적으로 바꾸면 됩니다.
