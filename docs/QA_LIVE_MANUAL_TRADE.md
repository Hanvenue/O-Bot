# 라이브 수동 거래 전 최종 QA 체크리스트

> 오봇으로 **수동 실제 거래** 테스트 전에 확인할 항목입니다. 문제되는 부분이 없으면 체크 후 진행하세요.

---

## 1. 환경·설정 (.env)

| 항목 | 확인 |
|------|------|
| **계정 1** | `OPINION_EOA_1`(또는 `OPINION_DEFAULT_EOA`), `OPINION_API_KEY_1`, `OPINION_PROXY_1` 설정 |
| **계정 2** | `OPINION_EOA_2`, `OPINION_API_KEY_2`, `OPINION_PROXY_2` 설정 |
| **CLOB 주문용** | 계정 1·2 각각 `OPINION_CLOB_PK_1`, `OPINION_CLOB_PK_2` 설정 (Multisig 없으면 EOA 사용) |
| **선택** | `OPINION_MULTISIG_1`, `OPINION_MULTISIG_2` (없으면 EOA로 주문) |
| **네트워크** | `BSC_RPC_URL` 필요 시 설정 (기본값: Binance 공개 RPC) |

- 자전거래는 **최소 2개 계정** 필요. Maker = 계정 1, Taker = 계정 2 순서로 사용됩니다.

---

## 2. 수동 거래 흐름 (동작 확인)

| 단계 | 내용 |
|------|------|
| 1 | **1시간 마켓 불러오기** → 시장·종료 시각·GAP 표시 확인 |
| 2 | **Shares** 1~1000 입력, UP/DOWN 비율·예상 거래액 갱신 확인 |
| 3 | **GAP → Maker 방향** 문구 확인 (예: `+200 → Maker UP`) |
| 4 | **수동 Go!** 한 번만 클릭 (연타 시 중복 주문 가능) |
| 5 | 성공 시: `실행 완료. 방향 UP, Maker: order_id, Taker: order_id` 표시 |
| 6 | 실패 시: 에러 메시지가 **한글/이해 가능한 문구**로 나오는지 확인 (원문 코드 노출 없음) |

---

## 3. 안전·에러 처리

| 항목 | 상태 |
|------|------|
| **시장 종료** | `time_remaining <= 0` 이면 `trade_ready=false`, 실행 차단 |
| **잔고 부족** | 실행 전 Maker/Taker 잔고 검사, 부족 시 한글 메시지 반환 |
| **Maker/Taker 동일** | 같은 계정이면 서버에서 `"Maker와 Taker는 서로 다른 계정이어야 합니다."` 반환 |
| **CLOB 미설정** | `OPINION_CLOB_PK_{id}` 없으면 `needs_clob` + 안내 메시지 |
| **Opinion API 에러** | CLOB/API 예외 시 `interpret_opinion_api_response()`로 사용자용 메시지 변환 후 UI 표시 |

---

## 4. 라이브 전 주의사항

- **Maker/Taker 고정:** 현재는 **계정 목록 1번 = Maker, 2번 = Taker**로 고정됩니다. 다른 조합을 쓰려면 .env에서 계정 순서를 바꾸거나, 추후 UI에서 Maker 선택 기능을 넣어야 합니다.
- **수동 Go! 한 번만:** 버튼 연타 시 Maker 주문이 여러 번 나갈 수 있으므로, 한 번 누르고 결과를 기다리세요.
- **접속 암호:** `app.py`의 `ACCESS_PASSWORD`는 라이브에서 강한 비밀번호로 변경 권장.
- **실패 시:** 미체결이면 10초 내 양쪽 주문 자동 취소 후 에러 메시지가 나옵니다. Maker만 체결된 경우 Opinion 웹에서 해당 주문 취소 여부를 확인하세요.

---

## 5. 코드 상 문제 없음 확인된 부분

- `execute_manual_trade` → `_run_wash_trade_via_clob`: 잔고 검사 → Maker LIMIT → 0.2초 대기 → Taker MARKET → 체결 폴링 → 미체결 시 양쪽 취소.
- `place_limit_order` / `place_market_order`: 예외 시 `interpret_opinion_api_response()` 사용.
- `get_1h_market_for_trade`: 시장 종료·호가 없음·토큰 없음 시 `trade_ready=false` 반환.
- Shares: 앱·백엔드 모두 1~1000 제한.

---

## 6. 체크리스트 (복사해서 사용)

```
[ ] .env 계정 1·2 (EOA, API_KEY, PROXY) 설정됨
[ ] .env CLOB: OPINION_CLOB_PK_1, OPINION_CLOB_PK_2 설정됨
[ ] 1시간 마켓 불러오기 → GAP·Maker 방향 표시 확인
[ ] 수동 Go! 1회 클릭 후 성공/실패 메시지 확인
[ ] 실패 시 한글 에러 메시지로 표시되는지 확인
[ ] (선택) 접속 암호·SECRET_KEY 프로덕션용으로 변경
```

위 항목 확인 후 라이브 수동 거래 테스트 진행하면 됩니다.
