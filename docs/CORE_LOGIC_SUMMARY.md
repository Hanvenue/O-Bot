# 이 프로젝트의 핵심 로직 요약본

> **대상 독자:** Claude Code. 리뷰/PR 시 전체 코드베이스를 탐색하지 않고, 이 문서만으로 프로젝트의 핵심 동작을 파악할 수 있도록 작성됨.

---

## 1. 프로젝트 정체 (한 줄)

- **오봇(O-Bot)** = **Opinion.trade** 전용 앱. 다중 지갑 로그인·수동/자동 예측 시장 거래만 담당.

---

## 2. 진입점과 라우트

| 진입점 | 역할 |
|--------|------|
| **`app.py`** | Flask 앱. Opinion 전용 라우트만 노출. |
| **라우트** | `/`, `/login`, `/api/opinion/*`, `/api/btc/price` 만 존재 (O-Bot 전용). |

- 프론트: `templates/opinion.html`, `templates/login.html` / `static/` (opinion.js, style.css, images/).

---

## 3. 핵심 모듈 (`core/`)

| 모듈 | 역할 (한 줄) |
|------|------------------|
| **opinion_config** | Opinion API·환경 설정 로드. |
| **opinion_account** | 계정/지갑 관련: 다중 로그인·세션·지갑 목록. |
| **opinion_client** | Opinion API HTTP 클라이언트(인증·요청/응답). |
| **opinion_btc_topic** | BTC 관련 토픽(마켓) 조회. |
| **opinion_manual_trade** | 수동 거래: 주문 생성·취소·1시간 마켓 자전거래 등. |
| **opinion_auto_trader** | 자동 거래 로직(전략·스케줄·실행). |
| **opinion_errors** | Opinion API 에러 응답 해석 → 사용자용 메시지로 변환. |
| **opinion_clob_order** | CLOB(Central Limit Order Book) 주문 처리. |
| **btc_price** | BTC 가격 조회(외부 소스). |
| **okx_balance** | OKX 잔고 조회(필요 시). |

- **에러 표시 규칙:** 401/404/429/500 등은 원문 그대로 노출하지 않고, `opinion_errors.interpret_opinion_api_response()`로 사용자용 메시지로 변환해 UI에 표시.

---

## 4. 데이터/API 흐름 (간단)

```
[브라우저] → app.py (Flask) → core/opinion_* (비즈니스 로직)
                                    ↓
                          Opinion.trade Open API (외부)
```

- 로그인/세션: `opinion_account` + Flask 세션.
- 거래: `opinion_client`로 API 호출 → `opinion_manual_trade` / `opinion_auto_trader`에서 주문·취소·전략 실행.
- 실패 시: `opinion_errors`에서 메시지 변환 후 JSON/HTML로 반환.

---

## 5. 설정

- **`config.py`** 존재. 오봇에서는 `Config.validate()` 호출하지 않는 것으로 정리됨.
- **`.env.example`** = Opinion·Flask·기타 환경 변수 예시.

---

## 6. 문서·규칙 (Claude Code가 보면 좋은 순서)

1. **`docs/CLAUDE_CODE_CONTEXT.md`** — 레포 구조·최근 변동·리뷰 시 토큰 절약 가이드.
2. **`docs/COLLAB_WORKFLOW.md`** — Cursor(구현) vs Claude(리뷰/PR) 역할·브랜치 규칙.
3. **`docs/OPINION_POINTS.md`** — Opinion PTS(포인트 시스템) 정리·API 한계(포인트 직접 조회 API 없음).
4. **`.cursorrules`** — 프로젝트 규칙·에러 표시 규칙·브랜치 작업 정리.

---

## 7. 리뷰/PR 시 (Claude Code용)

- **전체 코드 리뷰 금지.** 이 요약본 + `CLAUDE_CODE_CONTEXT.md`로 구조·역할을 이해한 뒤, **지정된 브랜치의 `git diff`만** 보고 리뷰·PR 작성.
- 새 Opinion API 호출이 있으면: 실패 시 `opinion_errors` 경유해 사용자용 메시지 반환 여부 확인.

---

*이 문서는 `docs/` 내 구조·문서와 `.cursorrules`를 바탕으로 작성되었으며, 실제 코드는 레포 루트 또는 `o-bot` 경로와 동기화되어 있을 수 있음.*
