#!/usr/bin/env python3
"""
Opinion.trade 프록시 동작 확인
- .env의 OPINION_PROXY(계정1), OPINION_PROXY_2(계정2)로 API 호출 테스트
- 사용: python3 scripts/test_opinion_proxy.py (프로젝트 루트에서)
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.chdir(root)

from dotenv import load_dotenv
load_dotenv()

from core.opinion_config import (
    OPINION_API_KEY,
    OPINION_PROXY,
    OPINION_DEFAULT_EOA,
    OPINION_API_KEY_2,
    OPINION_PROXY_2,
    OPINION_EOA_2,
    get_proxy_dict,
)
from core.opinion_client import get_positions


def test_one(name: str, api_key: str, proxy: str, eoa: str) -> bool:
    if not api_key or not proxy or not eoa:
        print(f"  [{name}] 건너뜀 (키/프록시/EOA 없음)")
        return False
    eoa = eoa.strip()
    if not eoa.startswith("0x"):
        eoa = "0x" + eoa
    print(f"  [{name}] EOA={eoa[:14]}... proxy={proxy.split(':')[0]} ... ", end="", flush=True)
    res = get_positions(eoa, api_key, proxy, page=1, limit=1)
    if res.get("ok"):
        print("OK")
        return True
    err = res.get("data") or res.get("error") or res.get("status_code")
    print("실패:", err)
    return False


def main():
    print("Opinion.trade 프록시 테스트 (get_positions 1건)")
    print("-" * 50)
    ok1 = test_one("계정1", OPINION_API_KEY, OPINION_PROXY or "", OPINION_DEFAULT_EOA or "")
    ok2 = test_one("계정2(Wallet 2)", OPINION_API_KEY_2 or "", OPINION_PROXY_2 or "", OPINION_EOA_2 or "")
    print("-" * 50)
    if ok1 and ok2:
        print("두 계정 모두 정상.")
    elif ok1 or ok2:
        print("일부만 성공. 실패한 계정은 docs/PROXY_TROUBLESHOOTING.md 참고.")
    else:
        print("모두 실패. docs/PROXY_TROUBLESHOOTING.md 참고.")


if __name__ == "__main__":
    main()
