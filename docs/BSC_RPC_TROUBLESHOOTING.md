# BSC / Maker 주문 실패 시

Maker 주문 시 **"BSC 컨트랙트 호출에 실패했습니다"** 가 나올 수 있습니다. 원인은 두 가지입니다.

---

## A. "contract deployed correctly and chain synced" (RPC는 연결됨)

RPC에는 연결되지만 **컨트랙트 호출 자체**가 실패하는 경우입니다.

| 가능한 원인 | 조치 |
|------------|------|
| **BNB 없음** (가스비 지불 불가) | CLOB에 쓰는 지갑(EOA 또는 Gnosis Safe)에 **BSC(BNB Chain)에서 소량 BNB**를 넣어 주세요. (예: 0.01 BNB) |
| USDT 사용 승인(allowance) 안 됨 | app.opinion.trade에서 해당 마켓으로 한 번 거래/승인 후 다시 시도. |
| RPC 노드 지연/장애 | 잠시 후 재시도 또는 `.env`의 `BSC_RPC_URL`을 다른 공개 RPC로 변경. |

---

## B. RPC 접속 실패 (서버에서 BSC로 아예 못 나가는 경우)

### 1. 서버에서 어떤 RPC가 되는지 확인

SSH로 서버 접속 후:

```bash
cd /home/ubuntu/O-Bot
python3 scripts/test_bsc_rpc.py
```

- `[OK]` 가 나온 RPC가 **되는** 주소입니다.
- `[FAIL]` 은 해당 서버에서 막혀 있거나 타임아웃인 경우입니다.

### 2. .env에 되는 RPC로 설정

테스트에서 OK가 나온 주소 중 하나를 `.env`에 넣습니다.

```bash
# 예: bsc.drpc.org 가 OK였다면
BSC_RPC_URL=https://bsc.drpc.org
```

저장 후 서비스 재시작:

```bash
sudo systemctl restart obot
```

### 3. 그래도 실패할 때

- **방화벽:** 서버 아웃바운드 **443(HTTPS)** 이 막혀 있지 않은지 확인.
- **리전:** 일부 BSC RPC는 특정 지역/데이터센터 IP를 제한할 수 있습니다. 다른 RPC를 여러 개 시도해 보세요.
- **직접 지정:** `.env`에 `BSC_RPC_FALLBACKS=https://주소1,https://주소2` 처럼 쉼표로 여러 개 넣으면, 기본 RPC 실패 시 이 목록 순서대로 재시도합니다.
