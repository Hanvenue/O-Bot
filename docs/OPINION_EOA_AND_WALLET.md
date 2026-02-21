# Opinion EOA vs OKX Wallet (전체 주소가 뭔지)

> Opinion 문서(`OPINION_WALLET_FUNDING.md`, Opinion 공식 Docs) 기준 정리.

---

## 결론: 전체 주소 = **주소**이지, PK가 아님

| 구분 | 설명 |
|------|------|
| **EOA (전체 주소)** | **0x + 40자 hex** 공개 주소. OKX Wallet에서 **BNB Chain(BSC)** 선택 시 보이는 **지갑 주소**. |
| **Private Key (PK)** | 그 주소를 **서명**할 때 쓰는 비밀키. 주소는 이 PK에서 **유도**됨. |

즉, `.env`의 `OPINION_DEFAULT_EOA`, `OPINION_EOA_2`에는 **OKX Wallet의 BNB Chain 주소**를 넣는 것이지, **PK를 넣는 게 아니다.**

---

## Opinion 문서 요약

1. **자금 위치**  
   - USDT는 **OKX Wallet EOA**가 **BNB Chain**에 들고 있는 그 주소에 있음.  
   - 즉 Opinion에서 쓰는 “내 주소” = **BNB Chain에서의 그 지갑 주소**.

2. **지갑 연결**  
   - OKX Wallet으로 연결하면, 그 지갑의 **EOA 주소**가 곧 “나의 거래 주소”.  
   - CLOB SDK의 `private_key`는 **그 EOA를 서명하는 키** = OKX Wallet의 (해당 체인) PK.

3. **EVM 호환**  
   - BNB Chain(BSC)은 이더리움과 같은 주소 체계.  
   - 같은 PK → 같은 **0x + 40자** 주소.  
   - 그래서 오봇 코드에서도 `eth_account`로 PK → EOA 계산하고, 그 EOA로 API 호출.

---

## OKX Wallet에서 “전체 주소” 복사하는 방법

1. OKX Wallet 앱/웹 열기  
2. **BNB Chain(BSC)** 네트워크 선택  
3. 해당 지갑의 **주소** 복사 (0x로 시작, 42자: 0x + 40 hex)  
4. 그 값을 `.env`의 `OPINION_EOA_2`(또는 `OPINION_DEFAULT_EOA`)에 넣기  

**주의:**  
- **Private Key(비밀키)** 를 넣으면 안 됨.  
- **주소(Address)** 만 넣어야 함.

---

## 요약 표

| .env 항목 | 넣는 값 |
|-----------|--------|
| `OPINION_DEFAULT_EOA` / `OPINION_EOA_2` | OKX Wallet **BNB Chain 주소** (0x + 40자 hex) |
| (로그인 시 UI에서 입력) | OKX Wallet **Private Key** (서명용, 저장 안 함) |

전체 주소 = OKX Wallet의 **Binance Chain(BSC) 주소**이고, **PK가 아니다.**
