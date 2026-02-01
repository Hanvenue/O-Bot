# 디버깅 변경 사항 (2025-02-01)

전체 코드 리뷰 후 수정한 버그 목록입니다.

---

## 🔴 치명적 버그 (수정됨)

### 1. Auto 모드에서 `trader`가 None이던 문제
- **원인**: `auto_trader.py`가 `from core.trader import trader`로 import하는데, `core.trader`의 `trader`는 `None`으로 고정되어 있었음.
- **수정**: `app.py`에서 Trader 인스턴스를 만든 뒤 `core.trader.trader`에 할당. `auto_trader`는 `trader_module.trader`를 참조하도록 변경.
- **영향**: Auto 모드 실행 시 `'NoneType' object has no attribute 'execute_wash_trade'` 에러 발생 → 수정으로 정상 동작.

---

## 🟡 로직/안정성 버그

### 2. 거래 실행 시 계정 부족 처리
- **원인**: `get_account_with_lowest_balance()`가 None을 반환할 때 `get_account(1)`도 None일 수 있음. `next()`로 taker 선택 시 계정이 1개일 때 `StopIteration` 발생.
- **수정**: maker/taker 선택 전에 유효성 검사 추가. 최소 2개 계정 필요 조건 명시.

### 3. 거래 성공 후 잘못된 잔액 업데이트
- **원인**: Auto 모드에서 거래 성공 시 maker 잔액을 단순히 빼는 로직은 자전거래 구조와 맞지 않음.
- **수정**: 해당 로직 제거. 실제 잔액은 Predict.fun API에서 조회해야 함.

### 4. Validator - end_time 형식
- **원인**: API/JSON에서 `end_time`이 문자열로 오면 `datetime - datetime` 연산 시 에러.
- **수정**: 문자열이면 `datetime.fromisoformat()`으로 파싱 후 검증.

### 5. Validator - orderbook 형식
- **원인**: `asks[0][0]`, `bids[0][0]` 가정. API에 따라 `[price, qty]` 또는 `{price: x, size: y}` 등 다양한 구조 가능.
- **수정**: `_extract_price()` 헬퍼 추가. 리스트/딕셔너리 형식 모두 처리. `optimal_price`는 최소 0.01로 제한.

### 6. API 입력값 검증
- **원인**: `market_id`, `shares`가 JSON에서 문자열로 올 수 있음. `shares`가 0이거나 음수일 수 있음.
- **수정**: `int()` 변환 및 유효 범위 검사 추가. `request.get_json()`이 None일 때를 대비한 fallback 추가.

---

## 🟢 개선 사항

### 7. Account 로딩
- **개선**: `private_key` 또는 `proxy`가 비어 있으면 해당 계정 건너뛰기. 전체 앱 시작 실패 대신 부분 로딩 허용.

### 8. Account.to_dict()
- **개선**: `proxy`가 None이면 `proxy.split(':')` 에러 방지를 위해 `proxy_ip`를 `'N/A'`로 처리.

### 9. 프론트엔드 (main.js)
- **개선**: `formatTime(undefined)` 시 `NaN` 방지. `market.price_gap`이 없을 때 기본값 0 사용. `addTradeToHistory`에서 `trade.price` 등이 없을 때 처리.

### 10. app.run() 설정
- **개선**: `host='0.0.0.0'`으로 복원 (같은 네트워크 내 다른 기기에서 접속 가능).

---

## 확인 방법

```bash
cd /Users/han/Downloads/gyeong-bot
source venv/bin/activate
python app.py
```

브라우저에서 `http://localhost:5000` 접속 후 다음을 확인:
- 대시보드 로딩
- `/api/status` 응답
- Auto 모드 시작/중지 (trader 연결 확인)
