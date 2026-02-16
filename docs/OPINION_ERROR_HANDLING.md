# Opinion.trade API 에러 처리 규칙

이 문서는 **Git/규칙 단일 기준**입니다. Opinion 관련 에러를 다룰 때 항상 이 규칙을 따릅니다.

---

## 1. 원칙

**Opinion.trade에서 400이 아닌 에러 코드(401, 404, 429, 500 등)를 반환하면, 그대로 UI로 내지 않고 해석해 저장한 다음, 사용자가 이해할 수 있는 에러 메시지로 보여 준다.**

- 원문(code, msg, body)은 로그 또는 내부 필드(`raw_message`, `error_code`)로만 보관.
- UI·API 응답의 `error`(또는 `user_message`)에는 **해석된 한글 메시지**만 넣는다.

---

## 2. 구현 위치

| 항목 | 위치 |
|------|------|
| **에러 코드 → 사용자 메시지 매핑** | `core/opinion_errors.py` |
| **Opinion API 응답 해석** | `interpret_opinion_api_response(status_code, body)` |
| **자동 Go! 등 사전 조건 메시지** | `get_auto_error_message(error_code)` |

---

## 3. 사용 방법

- 백엔드에서 Opinion API를 호출한 뒤 `ok`가 아니면:
  1. `interpret_opinion_api_response(res["status_code"], res.get("data"))` 호출.
  2. 반환된 `user_message`를 JSON의 `error`(또는 `user_message`)에 넣어 클라이언트에 전달.
- 자동 Go! 등 사전 검사 실패 시:
  - `get_auto_error_message("NO_API_KEY")` 등으로 메시지 조회 후 `error`에 넣어 반환.

---

## 4. 자동 Go! 가능 에러 코드 (에러 메시지 정리)

`POST /api/opinion/auto/start` 호출 시 아래 코드 중 하나가 반환될 수 있다. UI에는 `error`(사용자용 메시지)만 표시한다.

| error_code | 의미 | 사용자 메시지 (요약) |
|------------|------|----------------------|
| `NO_API_KEY` | API 키 미설정 | .env에 OPINION_API_KEY를 넣어 주세요. |
| `NO_PROXY` | 프록시 미설정 | .env에 OPINION_PROXY를 넣어 주세요. |
| `NEED_TWO_ACCOUNTS` | 계정 2개 미만 | 최소 2개 계정 로그인이 필요합니다. |
| `NO_MARKET` | 1시간 마켓 없음 | 진행 중인 마켓을 찾을 수 없습니다. 불러오기 후 다시 시도. |
| `CLOB_NOT_READY` | 주문 미연동 | CLOB SDK 연동 후 사용 가능. 당분간 수동 Go! 사용. |
| `ALREADY_RUNNING` | 이미 자동 실행 중 | 자동 거래가 이미 실행 중입니다. |
| `START_PRICE_FAILED` | Pyth 시작가 조회 실패 | 구간 시작 시 BTC 가격을 가져오지 못했습니다. |
| `TRADE_NOT_READY` | 거래 조건 미충족 | 호가창/시장 상태를 확인해 주세요. |
| `UNKNOWN` | 기타 오류 | 잠시 후 다시 시도해 주세요. |

전문 메시지 전문은 `core/opinion_errors.AUTO_ERROR_CODES`에 정의되어 있다.

---

## 5. 추가/수정 시

- 새 HTTP/API 코드나 새 에러 케이스가 생기면 `core/opinion_errors.py`에 메시지를 추가한다.
- 새 Opinion 연동 엔드포인트를 만들 때는 실패 시 위 해석 함수를 사용해 사용자용 메시지를 반환하도록 한다.
