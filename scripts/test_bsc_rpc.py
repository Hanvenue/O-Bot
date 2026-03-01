#!/usr/bin/env python3
"""
서버에서 BSC RPC 접속 가능 여부 확인
- Maker 주문 시 'BSC 컨트랙트 호출 실패'가 나면, 이 스크립트를 서버에서 실행해 보세요.
- 되는 RPC가 있으면 .env의 BSC_RPC_URL을 그 주소로 바꾸면 됩니다.

사용 (서버에서):
  cd /home/ubuntu/O-Bot && python3 scripts/test_bsc_rpc.py
"""
import json
import os
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.chdir(root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import requests

# .env 기준 + 기본 fallback 목록 (opinion_clob_order와 동일)
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/").strip()
_RAW = (os.getenv("BSC_RPC_FALLBACKS") or "").strip()
FALLBACKS = [u.strip() for u in _RAW.split(",") if u.strip()] or [
    "https://bsc-dataseed1.binance.org/",
    "https://bsc-dataseed2.binance.org/",
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-dataseed-public.bnbchain.org",
    "https://bsc-rpc.publicnode.com",
    "https://1rpc.io/bnb",
    "https://bsc.drpc.org",
    "https://bsc.publicnode.com",
    "https://bsc-dataseed.nariox.org",
    "https://bsc-dataseed.defibit.io",
    "https://binance.nodereal.io",
    "https://bsc-mainnet.public.blastapi.io",
]

# 중복 제거, BSC_RPC_URL 먼저
URLS = [BSC_RPC_URL]
for u in FALLBACKS:
    if u and u not in URLS:
        URLS.append(u)

PAYLOAD = {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}
TIMEOUT = 8


def test_url(url: str):
    try:
        t0 = time.perf_counter()
        r = requests.post(url, json=PAYLOAD, timeout=TIMEOUT)
        elapsed = time.perf_counter() - t0
        if r.status_code != 200:
            return False, elapsed, f"HTTP {r.status_code}"
        data = r.json()
        if data.get("error"):
            return False, elapsed, str(data["error"])
        result = data.get("result")
        if result is None:
            return False, elapsed, "no result"
        # BSC chainId = 0x38 = 56
        return True, elapsed, f"chainId={result}"
    except requests.exceptions.Timeout:
        return False, TIMEOUT, "timeout"
    except requests.exceptions.RequestException as e:
        return False, 0, str(e)[:80]
    except Exception as e:
        return False, 0, str(e)[:80]


def main():
    print("BSC RPC 접속 테스트 (서버에서 실행 중인지 확인용)\n")
    print("성공한 RPC가 있으면 .env에 BSC_RPC_URL=그주소 로 넣고 서비스 재시작하세요.\n")
    ok_list = []
    for url in URLS:
        success, elapsed, msg = test_url(url)
        status = "OK" if success else "FAIL"
        print(f"  [{status}] {url}")
        print(f"         {elapsed:.2f}s  {msg}")
        if success:
            ok_list.append(url)
    print()
    if ok_list:
        print("추천: .env에 아래 중 하나로 설정 후 재시작")
        for u in ok_list[:3]:
            print(f"  BSC_RPC_URL={u}")
    else:
        print("모든 RPC 실패. 방화벽/아웃바운드 443 허용, 또는 VPN/프록시 필요할 수 있습니다.")


if __name__ == "__main__":
    main()
