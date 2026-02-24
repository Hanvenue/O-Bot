# 자전거래(CLOB) 구현 검토 — .env에 PK만 넣었을 때

> 검토일: 현재 코드 기준 (feat/clob-sdk-integration 브랜치)

---

## 1. .env에 넣어야 하는 것

| 항목 | 필수 | 설명 |
|------|------|------|
| **OPINION_CLOB_PK_1** | ✅ | 계정1 지갑 Private Key (OKX Wallet 등에서 내보내기) |
| **OPINION_CLOB_PK_2** | ✅ | 계정2 지갑 Private Key |
| **OPINION_MULTISIG_1** / **_2** | ❌ (선택) | 생략 시 **해당 계정 EOA**를 자동 사용 (OPINION_DEFAULT_EOA / OPINION_EOA_2와 동일). |

코드상 `_get_clob_credentials()`는 **PK만** 있으면 되고, MULTISIG가 비어 있으면 **account.eoa**를 그대로 씁니다.  
그래서 **.env에는 PK만** 넣으면 됩니다.

---

## 2. 전제 조건 (이미 갖춰져 있어야 하는 것)

- **계정 2개**: `OPINION_DEFAULT_EOA` + `OPINION_EOA_2`, 각각 `OPINION_API_KEY` / `OPINION_API_KEY_2`, `OPINION_PROXY` / `OPINION_PROXY_2` 로 로드되는 상태.
- **1시간 마켓**: `get_1h_market_for_trade()`가 `trade_ready=True`, `yes_token_id`/`no_token_id` 반환.
- **최초 거래 시**: Opinion 측에서 **enable_trading()**(USDT 사용 승인)이 한 번은 되어 있어야 할 수 있음.  
  - 현재는 `place_order(..., check_approval=False)` 로 호출해서, **앱이 enable_trading을 호출하지 않음.**
  - 해당 지갑으로 **웹에서 한 번이라도 거래**했거나, 다른 경로로 승인이 되어 있으면 괜찮고,  
    처음 쓰는 지갑이면 **첫 주문이 “승인 안 됨” 등으로 실패할 수 있음.**

---

## 3. 흐름 검토 (이상적으로 동작하는지)

| 단계 | 구현 여부 | 비고 |
|------|-----------|------|
| 잔고 사전 검증 | ✅ | Maker/Taker 필요 금액 계산, 부족 시 에러 메시지 반환 |
| Maker LIMIT 주문 | ✅ | `market_id=topic_id`, `token_id`(UP이면 yes), `maker_price`, `size` |
| Taker 주문 (매칭) | ✅ | **실시간:** 기본 MARKET 주문으로 즉시 체결 시도. 반대 쪽 토큰, `taker_price`, 동일 `shares` |
| Maker 직후 대기 | ✅ | **실시간:** 2초 제거 → 0.2초만 대기 후 Taker 전송 |
| Maker/Taker order_id None 처리 | ✅ | 둘 다 None이면 Maker 취소 후 에러 반환 |
| 체결 폴링 (최대 10초) | ✅ | **실시간:** 0.4초 간격 폴링 (`get_order_status`) |
| 미체결 시 양쪽 취소 | ✅ | Maker/Taker 모두 취소 후 "미체결" 에러 반환 |
| 계정·CLOB 매칭 | ✅ | `account.id` → `OPINION_CLOB_PK_{id}`, MULTISIG 없으면 `account.eoa` 사용, `account.api_key`/`account.proxy` 일치 |

**정리:**  
설정(PK, API키, 프록시, 계정 2개)과 전제 조건만 맞으면, **자전거래 흐름 자체는 “이상적으로” 구현된 상태**로 보는 것이 맞습니다.

---

## 4. 확인이 필요한 부분 (실거래/API에 의존)

### 4.1 주문 응답에서 `order_id` 파싱

- `place_limit_order()` 안에서 `result.result.data.order_id` / `.id`, `result.result.order_id`, dict 형태 등 여러 경로를 시도하고 있음.
- **실제 Opinion CLOB API**가 `order_id`를 어떤 필드/구조로 주는지에 따라, **파싱 실패로 order_id가 None**이 될 수 있음.
- **권장:** 소액으로 한 번 실행해 보고, 실패 시 로그에 찍힌 `result` 구조를 확인한 뒤, 필요하면 `opinion_clob_order.py`의 order_id 추출 로직만 API 응답에 맞게 수정.

### 4.2 `get_order_status()`의 “체결(filled)” 판정

- `result.result.data`의 `status` / `order_status` / `filled` 등으로 판단하고,  
  `status_str in ("2", "filled", "FILLED", "2.0")` 이면 `filled=True`로 처리.
- Opinion API가 주문 상태를 **숫자(1/2/3)** 또는 **문자열**로 주는지는 문서/실제 응답 확인 필요.
- **잘못된 판정**이면:  
  - 체결됐는데 `filled=False`로 보이면 → 10초 후 양쪽 취소로 이어질 수 있고,  
  - 미체결인데 `filled=True`로 보이면 → 조기 성공 처리될 수 있음.  
- **권장:** 실거래 1회 후 `get_order_by_id` 응답 구조를 로그로 남기고, `get_order_status()`의 `filled`/`status` 해석이 그 구조와 일치하는지 검증.

### 4.3 최초 거래 실패 시 (enable_trading 미선행)

- **증상:** “Maker 주문 실패” 또는 SDK/API에서 승인/잔고 관련 에러.
- **대응:**  
  - 해당 지갑으로 **Opinion 웹에서 한 번이라도 거래**해 보거나,  
  - 또는 (SDK에서 지원한다면) `check_approval=True`로 한 번만 `place_order`를 호출해 보는 방식으로 **enable_trading 선행** 여부를 확인할 수 있음.  
  (현재 앱은 계속 `check_approval=False`만 사용.)

---

## 5. 결론

- **.env에는 PK만 넣으면 됩니다.** MULTISIG는 비어 두면 EOA와 동일하게 자동 사용됩니다.
- **그렇게 설정했을 때**,  
  - 계정 2개·API키·프록시·1시간 마켓·(필요 시) enable_trading 선행이 갖춰져 있으면,  
  - **자전거래 흐름(잔고 검사 → Maker → Taker → 체결 확인 → 미체결 시 취소)** 은 **이상적으로 구현되어 있다**고 볼 수 있습니다.
- **실제로 “이상적으로” 동작하는지** 확인하려면:
  1. **order_id** 파싱이 실제 API 응답과 맞는지,
  2. **get_order_status**의 **filled** 판정이 실제 상태값과 맞는지,  
  를 **소액 실거래 1회 + 로그 확인**으로 한 번 검증하는 것을 권장합니다.

---

## 6. 실시간 자전거래 (추가된 변경)

한 방향에서 거래를 올려도 **반대쪽이 바로 받지 못하면 실패**하는 구조이므로, 아래처럼 로직을 조정했습니다.

| 항목 | 기존 | 변경 후 |
|------|------|--------|
| Maker 직후 대기 | 2초 고정 | **0.2초** (`POST_MAKER_DELAY_SEC`) |
| Taker 주문 타입 | LIMIT | **MARKET** (기본, `USE_TAKER_MARKET_ORDER=true`) — 즉시 체결 시도 |
| 체결 폴링 간격 | 1.5초 | **0.4초** (`WASH_TRADE_POLL_INTERVAL_SEC`) |

- **설정:** `config.py` / `.env` 에서 `POST_MAKER_DELAY_SEC`, `WASH_TRADE_POLL_INTERVAL_SEC`, `WASH_TRADE_POLL_TIMEOUT_SEC`, `USE_TAKER_MARKET_ORDER` 로 조정 가능.
- Taker를 LIMIT로 쓰고 싶으면 `USE_TAKER_MARKET_ORDER=false` 로 두면 됩니다.
