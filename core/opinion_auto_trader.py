"""
오봇(Opinion) 자동 거래 - 1시간 마켓(Bitcoin Up or Down) 주기 검사 후 자전거래 실행
Flask(동기)에서 호출하므로 백그라운드 스레드 + time.sleep으로 루프 실행.
"""
import logging
import threading
import time
from datetime import datetime
from typing import Optional

from core.opinion_manual_trade import (
    get_1h_market_for_trade,
    execute_manual_trade,
)

logger = logging.getLogger(__name__)


class OpinionAutoTrader:
    """Opinion 1시간 마켓 자동 자전거래 엔진"""

    def __init__(self):
        self.is_running = False
        self.check_interval = 15  # 15초마다 조건 검사
        self.last_trade_time: Optional[datetime] = None
        self.trade_cooldown = 90  # 거래 후 90초 쿨다운
        self.shares_per_trade = 10

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

    def _can_trade(self) -> bool:
        if not self.last_trade_time:
            return True
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        return elapsed >= self.trade_cooldown

    def _loop(self):
        """주기적으로 1시간 마켓 조건 검사 후, trade_ready면 실행. (스레드에서 실행)"""
        while self.is_running:
            try:
                if not self._can_trade():
                    time.sleep(self.check_interval)
                    continue

                # 시간/갭 제한 적용 (종료 TIME_BEFORE_END 초 전부터만 진입)
                status = get_1h_market_for_trade(
                    topic_id=None,
                    skip_time_check=False,
                    shares=self.shares_per_trade,
                )

                if not status.get("trade_ready"):
                    reason = status.get("trade_reason") or status.get("error") or "대기 중"
                    logger.debug("Opinion auto: %s", reason)
                    time.sleep(self.check_interval)
                    continue

                topic_id = status.get("topic_id")
                if not topic_id:
                    time.sleep(self.check_interval)
                    continue

                logger.info(
                    "Opinion auto: 조건 충족 topic_id=%s direction=%s",
                    topic_id,
                    status.get("trade_direction"),
                )

                result = execute_manual_trade(
                    topic_id=topic_id,
                    shares=self.shares_per_trade,
                    direction=None,
                    maker_account_id=None,
                    taker_account_id=None,
                )
                self.last_result = result

                self.total_trades += 1
                # 쿨다운은 Maker 주문이 실제 제출된 경우에만 적용 (실패 시 즉시 재시도 가능)
                if result.get("success") or result.get("maker_order_id"):
                    self.last_trade_time = datetime.now()

                if result.get("success"):
                    self.successful_trades += 1
                    logger.info("Opinion auto trade OK: %s", result.get("direction"))
                else:
                    self.failed_trades += 1
                    err = result.get("error") or result.get("needs_clob") or "unknown"
                    logger.warning("Opinion auto trade failed: %s", err)

                time.sleep(self.check_interval * 2)
            except Exception as e:
                logger.exception("Opinion auto loop error: %s", e)
                time.sleep(self.check_interval)

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
            "account_id": None,
            "last_error": last_err,
            "last_result": self.last_result,
        }


opinion_auto_trader = OpinionAutoTrader()
