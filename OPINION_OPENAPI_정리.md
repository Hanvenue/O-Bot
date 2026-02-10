# Opinion.trade OpenAPI 개발자 문서 정리

> 출처: [Opinion OpenAPI Overview](https://docs.opinion.trade/developer-guide/opinion-open-api/overview)  
> 이 파일은 위 문서를 요약·정리한 것입니다.

---

## 1. Opinion OpenAPI가 뭔가요?

**비유**: Opinion이 운영하는 예측 시장(주식처럼 “이 일이 일어날까?”에 베팅하는 시장)의 **데이터만** 가져다 쓸 수 있는 창구라고 보면 됩니다.

- **RESTful API**: 웹 주소(URL)로 요청 보내면 JSON 데이터를 돌려줌
- **읽기 전용**: 시세·호가·거래량 등 **조회만** 가능하고, 주문·매매는 **이 API로는 안 됨**
- 주문·매매는 **Opinion CLOB SDK**(Python)를 써야 함

---

## 2. 이 API로 할 수 있는 것

| 기능 | 설명 (쉬운 말) |
|------|----------------|
| **시장 목록/정보** | 어떤 예측 시장이 있는지, 제목·상태·거래량 등 보기 |
| **가격 조회** | 특정 토큰의 최신 가격, 과거 가격 보기 |
| **호가창(오더북)** | 사려는 사람/팔려는 사람이 어떤 가격에 얼마나 있는지 보기 |
| **거래 통화 목록** | 어떤 통화(예: USDT 등)로 거래할 수 있는지 보기 |

---

## 3. 기본 주소와 인증

- **API 기본 주소**: `https://proxy.opinion.trade:8443/openapi`
- **인증**: 요청할 때 **API 키**를 헤더에 넣어야 함  
  - 헤더 이름: `apikey`  
  - 값: 발급받은 API 키

**API 키 받는 방법**:  
[신청 폼](https://docs.google.com/forms/d/1h7gp8UffZeXzYQ-lv4jcou9PoRNOqMAQhyW4IwZDnII) 작성 후 발급  
(같은 키로 OpenAPI, 웹소켓, CLOB SDK 모두 사용 가능)

---

## 4. 자주 쓰는 API 엔드포인트 요약

| 용도 | Method | 경로 | 설명 |
|------|--------|------|------|
| 시장 목록 | GET | `/market` | 조건에 맞는 시장 목록 (필터·정렬·페이지 가능) |
| 시장 상세 | GET | `/market/{marketId}` | 특정 시장 ID로 상세 정보 |
| 최신 가격 | GET | `/token/latest-price` | `token_id`로 해당 토큰 최신 체결가 |
| 호가창 | GET | `/token/orderbook` | `token_id`로 매수/매도 호가 목록 |
| 가격 히스토리 | GET | `/token/price-history` | `token_id`·`interval` 등으로 과거 가격 |
| 거래 통화 목록 | GET | `/quoteToken` | 사용 가능한 quote 토큰(통화) 목록 |

---

## 5. 요청 예시 (curl)

아래에서 `your_api_key`만 본인 API 키로 바꾸면 됩니다.

**시장 목록 (활성 시장, 24시간 거래량 순, 20개)**  
```bash
curl -X GET "https://proxy.opinion.trade:8443/openapi/market?status=activated&sortBy=5&limit=20" \
  -H "apikey: your_api_key"
```

**토큰 최신 가격**  
```bash
curl -X GET "https://proxy.opinion.trade:8443/openapi/token/latest-price?token_id=0x1234...5678" \
  -H "apikey: your_api_key"
```

**토큰 호가창**  
```bash
curl -X GET "https://proxy.opinion.trade:8443/openapi/token/orderbook?token_id=0x1234...5678" \
  -H "apikey: your_api_key"
```

**가격 히스토리 (일봉, 예: 30일)**  
```bash
curl -X GET "https://proxy.opinion.trade:8443/openapi/token/price-history?token_id=0x1234...5678&interval=1d" \
  -H "apikey: your_api_key"
```

---

## 6. 응답 형식

모든 응답은 아래 형태로 옵니다.

```json
{
  "code": 0,           // 0이면 성공, 0이 아니면 에러
  "msg": "success",   // 메시지
  "result": { ... }   // 실제 데이터 (엔드포인트마다 다름)
}
```

**에러 코드**  
| code | 의미 |
|------|------|
| 0 | 성공 |
| 400 | 잘못된 요청(파라미터 등) |
| 401 | 인증 실패 (API 키 잘못됨/없음) |
| 404 | 해당 자원 없음 |
| 429 | 요청 너무 많음 (속도 제한 초과) |
| 500 | 서버 쪽 오류 |

---

## 7. 제한 사항 (꼭 지킬 것)

| 항목 | 제한 |
|------|------|
| **초당 요청 수** | 15회/초 (API 키당) |
| **한 페이지 최대 개수** | 20개 |

초과하면 **429 Too Many Requests** 응답이 올 수 있음.

---

## 8. 지원 블록체인

| 체인 | Chain ID | 상태 |
|------|----------|------|
| BNB Chain Mainnet | 56 | ✅ 사용 가능 |

---

## 9. OpenAPI vs CLOB SDK (어떤 걸 쓸지)

| 기능 | OpenAPI (이 문서) | CLOB SDK |
|------|-------------------|----------|
| 시장/가격/호가/히스토리 조회 | ✅ | ✅ |
| 주문 넣기 | ❌ | ✅ |
| 주문 취소 | ❌ | ✅ |
| 포지션 관리 | ❌ | ✅ |
| 온체인 작업 | ❌ | ✅ |
| 사용 방식 | 어떤 언어나 HTTP 클라이언트 | Python |

**정리**:  
- **데이터만 보기**(대시보드, 모니터링, 분석) → **OpenAPI**  
- **실제 매매·주문·포지션** → **Opinion CLOB SDK**(Python)

---

## 10. 참고 링크

- **OpenAPI 문서**: https://docs.opinion.trade/developer-guide/opinion-open-api/overview  
- **API 키 신청**: https://docs.google.com/forms/d/1h7gp8UffZeXzYQ-lv4jcou9PoRNOqMAQhyW4IwZDnII  
- **CLOB SDK (Python)**: https://github.com/opinion-labs/opinion-clob-sdk  
- **PyPI**: https://pypi.org/project/opinion-clob-sdk/

---

*이 요약은 위 공식 문서를 바탕으로 정리했으며, 최신 스펙은 항상 Opinion 공식 문서를 참고하는 것이 좋습니다.*
