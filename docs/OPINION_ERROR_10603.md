# Opinion CLOB 에러 10603: Asset owner must be the current multi-signature wallet

> Opinion 문서 검토 후 원인·해결 정리.

---

## 1. 에러 메시지

```
Maker 주문 실패: [10603] Asset owner must be the current multi-signature wallet
```

---

## 2. Opinion 문서 기준 개념

- **`multi_sig_addr`**  
  자산(USDT·포지션)을 보유한 **지갑 주소**.  
  문서: *"Your wallet address ... can be found in your Opinion platform **My Profile** section"*

- **`private_key`**  
  주문에 **서명**하는 키. `multi_sig_addr`와 같은 EOA일 수 있고, 다를 수 있음(예: Gnosis Safe 소유자 키).

- **"current multi-signature wallet"**  
  Opinion 쪽에서 **이 계정/API 키에 연결된 “현재” 자산 보유 지갑**을 의미하는 표현으로 보임.  
  즉, **우리가 보내는 `multi_sig_addr`**가 **Opinion이 기대하는 “현재 지갑”**과 같아야 함.

---

## 3. 원인 정리

에러가 나는 이유는 다음이 **일치하지 않을 때**입니다.

| 구분 | 설명 |
|------|------|
| **우리가 보내는 주소** | `OPINION_MULTISIG_{id}`가 없으면 **CLOB PK에서 파생한 EOA**를 `multi_sig_addr`로 전송 |
| **Opinion이 기대하는 주소** | 해당 API 키(또는 계정)에 연결된 “현재” 자산 보유 지갑 (웹에서 연결한 지갑 또는 API 신청 시 기재한 주소) |

가능한 경우:

1. **API 키 발급 시** 다른 지갑 주소를 기재했고, 지금 CLOB에 넣은 PK는 그 지갑이 아님.
2. **app.opinion.trade**에서 로그인/연결한 지갑이 **CLOB PK에서 나온 지갑과 다름** (다른 지갑으로 연결해 둔 상태).
3. **OPINION_MULTISIG_1**에 예전에 쓰던 주소나 다른 지갑 주소가 들어가 있음.

---

## 4. 5분 해결 (10603 나올 때 바로 하기)

1. 브라우저에서 `https://내서버/api/opinion/clob-debug` 접속 → `multi_sig_addr_sent` 확인.
2. [app.opinion.trade](https://app.opinion.trade) 로그인(CLOB PK와 같은 지갑) → **My Profile**에서 지갑 주소 **전체** 복사(0x 포함 42자리).
3. 서버 `.env`에서 `OPINION_MULTISIG_1=` 또는 `OPINION_MULTISIG_2=` 뒤에 **그 주소 그대로** 붙여넣기.
4. 서버 재시작 (README 운영 명령어: `sudo systemctl restart obot`).
5. 다시 수동 Go! → My Profile 주소와 3번이 **완전히 같아야** 함.

---

## 5. 해결 체크리스트 (상세)

1. **CLOB PK와 “한 지갑”으로 맞추기**  
   - `OPINION_CLOB_PK_1` = **실제로 USDT/포지션을 보유한 OKX 지갑의 Private Key**인지 확인.  
   - 그 PK에서 나온 주소를 아래에서 사용.

2. **Opinion 웹에서 같은 지갑 연결**  
   - [app.opinion.trade](https://app.opinion.trade) 접속 → **같은 OKX 지갑(위 주소)**으로 연결 후 로그인(서명).  
   - “My Profile” 등에서 보이는 주소가 **PK에서 파생한 주소와 동일한지** 확인.

3. **.env에서 MULTISIG 정리**  
   - EOA만 쓸 때: **`OPINION_MULTISIG_1`(또는 _2) 비우기 또는 삭제.**  
   - 그러면 코드가 **PK에서 파생한 EOA**를 `multi_sig_addr`로 씀.  
   - Gnosis Safe를 쓰는 경우에만 `OPINION_MULTISIG_1`에 Safe 컨트랙트 주소를 명시.

4. **API 키와 지갑 관계**  
   - API 키 신청 시 특정 지갑 주소를 적었다면, 그 주소 = **PK에서 파생한 주소**여야 함.  
   - 다르면 Opinion 지원에 “API 키에 연결된 지갑 주소 변경” 요청이 필요할 수 있음.

---

## 6. 요약 (한 줄)

| 항목 | 내용 |
|------|------|
| **에러 의미** | 우리가 보낸 “자산 보유 주소”(multi_sig_addr)가 Opinion이 인식한 “현재 지갑”과 다름. |
| **우리 코드** | MULTISIG 미설정 시 CLOB PK에서 EOA 파생 → 그 주소를 multi_sig_addr로 전송. |
| **확인할 것** | (1) CLOB PK = 실제 자산 보유 지갑의 PK, (2) 웹에서 같은 지갑 연결, (3) MULTISIG 비우기(EOA만 쓸 때). |

---

## 7. 참고

- [Connect with Web3 wallet | Opinion Docs](https://docs.opinion.trade/trade-on-opinion.trade/connect-with-web3-wallet)
- [Opinion CLOB SDK – Configuration / Client](https://docs.opinion.trade/developer-guide/opinion-clob-sdk/)
- 프로젝트 내: `core/opinion_clob_order.py` → `_get_clob_credentials()` (MULTISIG 없을 때 PK에서 EOA 파생)
