"""
오봇 수동/자동 거래 결과 누적 저장 및 조회.
data/trade_history.json에 append, Overall·직전 거래 표시용.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_HISTORY_FILE = _DATA_DIR / "trade_history.json"
_MAX_RECORDS = 500


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_trade(record: Dict[str, Any]) -> None:
    """거래 1건 추가. record: ts, direction, shares, maker_amount_usd, taker_amount_usd, success, source, ..."""
    _ensure_dir()
    record = {k: v for k, v in record.items() if v is not None or k in ("maker_order_id", "taker_order_id", "error")}
    try:
        existing: List[Dict] = []
        if _HISTORY_FILE.exists():
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                if raw:
                    existing = json.loads(raw)
        existing.append(record)
        if len(existing) > _MAX_RECORDS:
            existing = existing[-_MAX_RECORDS:]
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=0)
    except Exception as e:
        logger.warning("trade_history append failed: %s", e)


def get_trade_history(limit: int = 50) -> Dict[str, Any]:
    """최근 거래 목록 + 누적 요약."""
    _ensure_dir()
    trades: List[Dict] = []
    if _HISTORY_FILE.exists():
        try:
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                if raw:
                    trades = json.loads(raw)
        except Exception as e:
            logger.warning("trade_history read failed: %s", e)
    trades = trades[-limit:] if limit else trades
    # 집계는 자전 완료(round_trip_completed=True)인 건만. 미체결/구버전 건은 목록에는 보이지만 합계·성공 횟수에서 제외.
    completed = [t for t in trades if t.get("round_trip_completed") is True]
    total_maker = sum(float(t.get("maker_amount_usd") or 0) for t in completed)
    total_taker = sum(float(t.get("taker_amount_usd") or 0) for t in completed)
    success_count = len(completed)
    return {
        "trades": list(reversed(trades)),
        "total_count": len(trades),
        "total_maker_usd": round(total_maker, 2),
        "total_taker_usd": round(total_taker, 2),
        "success_count": success_count,
    }
