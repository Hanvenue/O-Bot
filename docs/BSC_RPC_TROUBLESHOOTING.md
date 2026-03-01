# BSC RPC 접속 실패 시 (Maker 주문 실패)

Maker 주문 시 **"BSC(이더리움) 컨트랙트 호출에 실패했습니다"** 가 나오면, 서버에서 BSC RPC(블록체인 노드)에 접속이 안 되는 경우입니다.

## 1. 서버에서 어떤 RPC가 되는지 확인

SSH로 서버 접속 후:

```bash
cd /home/ubuntu/O-Bot
python3 scripts/test_bsc_rpc.py
```

- `[OK]` 가 나온 RPC가 **되는** 주소입니다.
- `[FAIL]` 은 해당 서버에서 막혀 있거나 타임아웃인 경우입니다.

## 2. .env에 되는 RPC로 설정

테스트에서 OK가 나온 주소 중 하나를 `.env`에 넣습니다.

```bash
# 예: bsc.drpc.org 가 OK였다면
BSC_RPC_URL=https://bsc.drpc.org
```

저장 후 서비스 재시작:

```bash
sudo systemctl restart obot
```

## 3. 그래도 실패할 때

- **방화벽:** 서버 아웃바운드 **443(HTTPS)** 이 막혀 있지 않은지 확인.
- **리전:** 일부 BSC RPC는 특정 지역/데이터센터 IP를 제한할 수 있습니다. 다른 RPC를 여러 개 시도해 보세요.
- **직접 지정:** `.env`에 `BSC_RPC_FALLBACKS=https://주소1,https://주소2` 처럼 쉼표로 여러 개 넣으면, 기본 RPC 실패 시 이 목록 순서대로 재시도합니다.
