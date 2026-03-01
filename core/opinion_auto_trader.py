"""
오봇(Opinion) 자동 거래 - 1시간 마켓(Bitcoin Up or Down) 주기 검사 후 자전거래 실행
Flask(동기)에서 호출하므로 백그라운드 스레드 + time.sleep으로 루프 실행.
"""
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional

from core.opinion_manual_trade import (
    get_1h_market_for_trade,
    execute_manual_trade,
)

logger = logging.getLogger(__name__)

_AUTO_INTERVAL = int(os.getenv("AUTO_TRADE_INTERVAL_SEC", "3600").strip() or "3600")


class OpinionAutoTrader:
    """Opinion 1시간 마켓 자동 자전거래 엔진. 1시간(또는 AUTO_TRADE_INTERVAL_SEC)마다 1회, Maker 수수료 없음 유지."""

    def __init__(self):
        self.is_running = False
        self.interval_seconds = max(60, _AUTO_INTERVAL)  # 기본 3600(1시간). 테스트 시 .env에 60 등 설정
        self.shares_per_trade = 10
        self.maker_account_id: Optional[int] = None

        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.last_result: Optional[dict] = None  # UI/직전 거래 카드용

        self._thread: Optional[threading.Thread] = None

    def start(self, shares: int = 10, account_id: Optional[int] = None) -> dict:
        """
        자동 거래 시작. 백그라운드 스레드에서 루프 실행.
        Returns:
            {"success": True} 또는 이미 실행 중이면 {"success": False, "error": "..."}
        """
        if self.is_running:
            return {"success": False, "error": "자동 거래가 이미 실행 중입니다."}
        self.is_running = True
        self.shares_per_trade = max(1, int(shares))
        self.maker_account_id = account_id
        logger.info("Opinion auto trader started (shares=%s)", self.shares_per_trade)

        def run_loop():
            try:
                self._loop()
            except Exception as e:
                logger.exception("Opinion auto loop error: %s", e)
            finally:
                self.is_running = False
                logger.info("Opinion auto loop ended")

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        return {"success": True}

    def stop(self):
        self.is_running = False
        logger.info("Opinion auto trader stopped")
        return {"success": True}

    def _loop(self):
        """1시간마다 1회 자동 거래 (표시된 Share만큼). 스레드에서 실행."""
        import time as _time
        while self.is_running:
            try:
                _time.sleep(self.interval_seconds)
                if not self.is_running:
                    break

                status = get_1h_market_for_trade(
                    topic_id=None,
                    skip_time_check=False,
                    shares=self.shares_per_trade,
                )
                if not status.get("trade_ready"):
                    logger.info("Opinion auto: 조건 미충족, 다음 1시간 후 재시도. %s", status.get("trade_reason") or status.get("error"))
                    continue
                topic_id = status.get("topic_id")
                if not topic_id:
                    continue

                logger.info("Opinion auto: 1회 거래 실행 topic_id=%s direction=%s shares=%s", topic_id, status.get("trade_direction"), self.shares_per_trade)
                result = execute_manual_trade(
                    topic_id=topic_id,
                    shares=self.shares_per_trade,
                    direction=None,
                    maker_account_id=self.maker_account_id,
                    taker_account_id=None,
                )
                self.last_result = result
                self.total_trades += 1
                if result.get("success"):
                    self.successful_trades += 1
                    logger.info("Opinion auto trade OK: %s", result.get("direction"))
                else:
                    self.failed_trades += 1
                    logger.warning("Opinion auto trade failed: %s", result.get("error"))

                try:
                    # 자전 완료(양쪽 체결)된 거래만 Overall에 기록.
                    if result.get("round_trip_completed") is True:
                        from core.trade_history import append_trade
                        rec = {
                            "ts": int(time.time()),
                            "direction": result.get("direction"),
                            "shares": result.get("shares"),
                            "maker_amount_usd": result.get("maker_amount_usd"),
                            "taker_amount_usd": result.get("taker_amount_usd"),
                            "maker_order_id": result.get("maker_order_id"),
                            "taker_order_id": result.get("taker_order_id"),
                            "success": True,
                            "round_trip_completed": True,
                            "source": "auto",
                        }
                        append_trade(rec)
                except Exception as e2:
                    logger.debug("trade_history append auto: %s", e2)
            except Exception as e:
                logger.exception("Opinion auto loop error: %s", e)

    def get_statistics(self) -> dict:
        rate = (
            (self.successful_trades / self.total_trades * 100)
            if self.total_trades > 0
            else 0
        )
        return {
            "is_running": self.is_running,
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": round(rate, 1),
            "shares_per_trade": self.shares_per_trade,
            "last_result": self.last_result,
        }

    def get_stats(self) -> dict:
        """API/UI용 별칭. get_statistics()와 동일."""
        return self.get_statistics()

    def get_status(self) -> dict:
        """API용: 실행 여부, 마지막 결과 요약."""
        last_err = None
        if self.last_result and not self.last_result.get("success"):
            last_err = self.last_result.get("error") or (
                "CLOB 미연동" if self.last_result.get("needs_clob") else "실패"
            )
        return {
            "running": self.is_running,
            "account_id": self.maker_account_id,
            "last_error": last_err,
            "last_result": self.last_result,
        }


opinion_auto_trader = OpinionAutoTrader()
