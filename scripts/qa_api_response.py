#!/usr/bin/env python3
"""
QA: Predict.fun API 응답 구조 확인 (가격 갭 디버깅용)
로컬 .env의 PREDICT_API_KEY 사용
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import requests

API_KEY = os.getenv("PREDICT_API_KEY", "").strip()
API_KEY = "".join(c for c in API_KEY if ord(c) < 128 and (c.isalnum() or c in "-"))
BASE = "https://api.predict.fun"

def main():
    if not API_KEY:
        print("❌ PREDICT_API_KEY required in .env")
        return 1
    headers = {"x-api-key": API_KEY}
    params = {"marketVariant": "CRYPTO_UP_DOWN", "status": "OPEN", "first": 5}
    r = requests.get(f"{BASE}/v1/categories", headers=headers, params=params, timeout=10)
    if not r.ok:
        print(f"❌ API error {r.status_code}: {r.text[:200]}")
        return 1
    data = r.json()
    cats = data.get("data") or []
    print(f"✅ Categories: {len(cats)}")
    for i, cat in enumerate(cats[:2]):
        vd = cat.get("variantData") or {}
        sp = vd.get("startPrice") or cat.get("startPrice")
        print(f"  Category {i}: variantData.startPrice={sp}, title={cat.get('title','')[:50]}")
        for m in (cat.get("markets") or [])[:1]:
            vm = m.get("variantData") or {}
            msp = vm.get("startPrice") or m.get("_categoryStartPrice")
            print(f"    Market {m.get('id')}: variantData.startPrice={vm.get('startPrice')}, _categoryStartPrice=N/A (set by us)")
    # Fetch one market by ID
    if cats and cats[0].get("markets"):
        mid = cats[0]["markets"][0].get("id")
        if mid:
            r2 = requests.get(f"{BASE}/v1/markets/{mid}", headers=headers, timeout=10)
            if r2.ok:
                mdata = r2.json().get("data") or {}
                v = mdata.get("variantData") or {}
                print(f"\n✅ Market {mid} detail: variantData.startPrice={v.get('startPrice')}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
