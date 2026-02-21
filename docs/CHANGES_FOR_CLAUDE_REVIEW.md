# 브랜치 feat/env-template — 변경 사항 요약 (Claude 리뷰용)

> 이 브랜치는 `feat/clob-sdk-integration` 에서 분기했으며, CLOB 연동·실시간 자전거래·env/계정 확장·계정 2 IP 표시 수정 등을 포함합니다.

---

## 1. .env / 계정 확장

| 파일 | 변경 요약 |
|------|-----------|
| **.env.example** | 주석 정리, 실시간 자전거래 옵션 블록 제거(코드 기본값 사용). 계정 3+ 패턴 안내 추가(OPINION_EOA_3, OPINION_API_KEY_3, OPINION_PROXY_3). OKX Wallet BNB Chain PK 형식 명시. |
| **env.template** | 주석 없는 최소 변수 목록만 담은 복사용 템플릿 추가. |
| **core/opinion_config.py** | `.env` 명시적 load_dotenv. `get_env_accounts()` 추가 — OPINION_EOA_N, OPINION_API_KEY_N, OPINION_PROXY_N (N=1~20) 순서로 읽어 계정 목록 반환. 계정 1은 기존 이름(OPINION_DEFAULT_EOA, OPINION_API_KEY, OPINION_PROXY) 호환. `has_proxy()`는 get_env_accounts() 기반으로 변경. |
| **core/opinion_account.py** | 계정 1·2 하드코딩 제거. `_load()`에서 `get_env_accounts()` 결과로 계정 생성(Wallet 01, 02, …). `_ensure_env_loaded()`로 요청 시점에 .env 재로드. `get_all()` 호출 시마다 `_load()` 호출해 최신 .env 반영. PK 로그인 시 EOA 매칭도 get_env_accounts()로 N개 계정 지원. |

---

## 2. 계정 2 IP 표시 수정

| 파일 | 변경 요약 |
|------|-----------|
| **core/opinion_account.py** | `_proxy_display_host(proxy_str)` 추가 — IP:PORT:USER:PASS, USER:PASS@IP:PORT 등 여러 형식에서 IP/호스트 추출. `to_dict()`에서 proxy_preview에 사용, 없으면 "—". |

---

## 3. CLOB / 실시간 자전거래 (이전 브랜치 포함)

| 파일 | 변경 요약 |
|------|-----------|
| **core/opinion_clob_order.py** | `_place_order_impl`, `place_limit_order`, `place_market_order` 분리. Taker용 MARKET 주문 지원. |
| **core/opinion_manual_trade.py** | Maker 직후 대기 2초 → 0.2초. Taker 기본 MARKET 주문. 폴링 0.4초. GAP 200달러 기준 Maker 방향(UP/DOWN) 결정. |
| **config.py** | POST_MAKER_DELAY_SEC, WASH_TRADE_POLL_*, USE_TAKER_MARKET_ORDER 등 실시간 자전거래 옵션 추가. |

---

## 4. UI / API

| 파일 | 변경 요약 |
|------|-----------|
| **app.py** | 수동 거래 execute 시 direction 없으면 서버 trade_direction 사용. execute_manual_trade 인자 정리(maker_account_id). |
| **templates/opinion.html** | GAP → Maker 표시 영역(sharesGapDirection, sharesGapText) 추가. |
| **static/js/opinion.js** | status 응답에서 trade_direction, btc_gap_usd 저장·표시. 수동 Go! 시 body.direction으로 서버 추천 방향 전달. |

---

## 5. 문서

| 파일 | 변경 요약 |
|------|-----------|
| **docs/CLOB_WASH_TRADE_REVIEW.md** | 자전거래 검토, §6 실시간 변경 사항 추가. |
| **docs/COLLAB_WORKFLOW.md** | 최근 작업 브랜치 명시. |
| **docs/PROMPT_CLAUDE_REVIEW.md** | 브랜치명·요약 갱신(아래에서 최종 반영). |
| **docs/현재_작업_상태.md** | 실시간 자전거래 요약 등. |
| **docs/OPINION_EOA_AND_WALLET.md**, **PROXY_TROUBLESHOOTING.md** | 신규 추가. |

---

## 6. 삭제·기타

| 항목 | 설명 |
|------|------|
| **삭제** | account.py, index.html, main.js, market.py, style.css, validator.py (오봇 전용 구조 정리). |
| **추가** | core/opinion_geo.py (IP→국가/깃발), scripts/test_opinion_proxy.py. |

---

## 리뷰 시 참고

- **O-Bot 전용.** 경봇(gyeong-bot) 미포함.
- **기존 .env 호환:** 계정 1(OPINION_DEFAULT_EOA, OPINION_API_KEY, OPINION_PROXY), 계정 2(OPINION_EOA_2, OPINION_API_KEY_2, OPINION_PROXY_2) 그대로 동작.
- **확장:** 계정 3 이상은 OPINION_EOA_N, OPINION_API_KEY_N, OPINION_PROXY_N 으로 추가 가능.
