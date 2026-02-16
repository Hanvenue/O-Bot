# Opinion.trade 지갑·자금 구조 (배팅 시 누가 송금하나?)

> Opinion 공식 문서·CLOB SDK 문서를 바탕으로 정리했습니다.  
> 최신 내용은 [Opinion Docs](https://docs.opinion.trade/)를 참고하세요.

---

## 1. 결론: OKX Wallet에서 바로 쓰는 구조 (가상 지갑 아님)

**Opinion.trade에 배팅할 때:**

- **OKX Wallet(또는 연결한 Web3 지갑)의 EOA 주소에 있는 USDT를 그대로 사용**합니다.
- “Opinion 전용 가상 지갑에 입금해서 그 안에서만 거래”하는 구조가 **아닙니다**.

비유하면:

- **가상 지갑 구조**: 거래소에 돈을 넣어두고, 거래소 잔액으로만 매매 (예: 중앙화 거래소 잔고).
- **Opinion 구조**: 내 지갑(OKX Wallet EOA)에 USDT가 있고, 그 돈에 대한 **사용 승인**만 블록체인에 한 번 올려두고, 이후 주문은 **서명만** 보내서 체결. 돈은 계속 **내 지갑**에 있다가, 거래가 일어날 때만 컨트랙트가 사용.

---

## 2. 자금이 어디 있나?

| 구분 | 설명 |
|------|------|
| **담보(USDT) 위치** | 사용자 EOA 지갑 (OKX Wallet 등) **BNB Chain** 에 있는 USDT |
| **포지션/결과 토큰** | ConditionalTokens 컨트랙트와 연동된 온체인 포지션 (같은 EOA 또는 `multi_sig_addr`) |
| **Opinion 전용 입금 지갑** | ❌ 없음. 별도 “Opinion 가상 지갑”에 입금·출금하는 구조 아님 |

즉, **OKX Wallet에서 바로 송금(사용)하는 구조**에 가깝고, “Opinion용 가상 지갑에서 송금”하는 구조는 아닙니다.

---

## 3. 실제로 일어나는 일 (요약)

1. **지갑 연결**  
   - OKX Wallet 등 Web3 지갑으로 연결 → 그 지갑의 **EOA 주소**가 곧 “나의 거래 주소”.

2. **최초 1회: 사용 승인 (온체인)**  
   - `enable_trading()` 호출 → “내 USDT를 Opinion 관련 컨트랙트가 쓰는 것”을 허용.  
   - BNB Chain에서 **가스비(BNB)** 소모. (보통 $0.005~0.05 수준)

3. **거래 전: USDT → YES/NO 토큰 (온체인)**  
   - `split()` 호출 → USDT를 해당 시장의 YES/NO 결과 토큰으로 바꿈.  
   - 역시 **가스비(BNB)** 필요.

4. **주문 넣기·취소 (가스 무료)**  
   - 주문·취소는 **오프체인 서명**만 보냄.  
   - 체결 시 컨트랙트가 이미 승인된 USDT/토큰을 사용.

5. **정산·회수**  
   - `merge()`, `redeem()` 등으로 결과 토큰을 다시 USDT로 되돌리거나 상환.  
   - 이 단계도 **온체인**, 가스비(BNB) 필요.

---

## 4. CLOB SDK 쪽 개념 (참고)

- **`private_key`**  
  - 주문·트랜잭션에 **서명**하는 EOA (우리 프로젝트에서는 OKX Wallet PK에서 나온 주소).
- **`multi_sig_addr`** (선택)  
  - 실제 USDT·포지션을 들고 있는 주소.  
  - `private_key`와 **같은 주소**로 둘 수 있고, 보안을 위해 **다른 주소**(예: 콜드/멀티시그)로 둘 수도 있음.

같은 EOA를 쓰면: **OKX Wallet 한 개로 “서명 + 자금” 모두 처리** = “OKX Wallet에서 바로 송금(사용)”하는 구조와 동일하게 동작합니다.

---

## 5. 문서 검토 요약

| 질문 | 답 |
|------|----|
| 배팅 시 OKX Wallet에서 바로 송금하는 구조? | ✅ **예.** USDT는 OKX Wallet EOA에 있고, 승인 후 그 USDT로 거래. |
| Opinion 전용 가상 지갑에 입금해서 쓰는 구조? | ❌ **아니요.** 그런 “입금용 가상 지갑”은 없음. |

---

## 6. 참고 링크

- [Connect with Web3 wallet | Opinion Docs](https://docs.opinion.trade/trade-on-opinion.trade/connect-with-web3-wallet)
- [Opinion CLOB SDK – Architecture / Client / FAQ](https://docs.opinion.trade/developer-guide/opinion-clob-sdk/)
- [OpenAPI 개요 정리](./OPINION_OPENAPI.md)
