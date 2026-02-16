"""
BTC Price Module - 실시간 Bitcoin 시세 (Pyth Network)
- REST: 한 번 조회 (fallback)
- SSE 스트림: Pyth Hermes v2 /v2/updates/price/stream 으로 실시간 수신, 캐시 갱신
"""
import json
import logging
import threading
import time

import requests

from config import Config

logger = logging.getLogger(__name__)

# SSE 스트림으로 받은 최신 가격 캐시 (스레드에서 갱신)
_stream_price: float | None = None
_stream_updated: float = 0.0
_stream_stop = threading.Event()
_stream_thread: threading.Thread | None = None

# 스트림 가격 유효 시간(초). 이 시간 지나면 get_current_price()가 REST로 fallback
STREAM_PRICE_MAX_AGE = 120

# 특정 시점 가격 캐시 (topic 구간당 1회만 Pyth Benchmarks 호출). key: start_ts(초), value: 가격
_price_at_ts_cache: dict[int, float] = {}
PYTH_BENCHMARKS_URL = "https://benchmarks.pyth.network"


def _parse_pyth_stream_data(data: dict) -> float | None:
    """Pyth SSE 'data:' 페이로드에서 BTC 가격 추출. parsed[0].price (price, expo)."""
    try:
        parsed = data.get("parsed") or []
        if not parsed:
            return None
        price_info = parsed[0].get("price") or {}
        p = int(price_info.get("price", 0))
        expo = int(price_info.get("expo", 0))
        return float(p * (10 ** expo))
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _run_btc_stream():
    """백그라운드: Pyth Hermes SSE 스트림 연결, 수신 시 캐시 갱신."""
    global _stream_price, _stream_updated
    feed_id = getattr(Config, "BTC_PRICE_FEED_ID", "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43")
    url = f"https://hermes.pyth.network/v2/updates/price/stream?ids[]={feed_id}"
    logger.info("BTC 실시간 시세 스트림 연결 중: %s", url)
    while not _stream_stop.is_set():
        try:
            resp = requests.get(
                url,
                stream=True,
                headers={"Accept": "text/event-stream"},
                timeout=30,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if _stream_stop.is_set():
                    break
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if decoded.startswith("data:"):
                    try:
                        payload = json.loads(decoded[5:].strip())
                        price = _parse_pyth_stream_data(payload)
                        if price is not None and price > 0:
                            _stream_price = price
                            _stream_updated = time.time()
                            logger.debug("BTC 시세 갱신: $%s", f"{price:,.2f}")
                    except json.JSONDecodeError:
                        pass
        except requests.exceptions.RequestException as e:
            logger.warning("BTC 스트림 연결 끊김: %s, 5초 후 재연결", e)
        except Exception as e:
            logger.exception("BTC 스트림 오류: %s", e)
        if not _stream_stop.is_set():
            time.sleep(5)


class BTCPriceService:
    """실시간 BTC/USD 시세 (Pyth Network REST + 선택적 SSE 스트림)"""

    def __init__(self):
        self.api_url = Config.PYTH_API_URL
        self.feed_id = Config.BTC_PRICE_FEED_ID

    def start_stream(self):
        """Pyth Hermes SSE 스트림 시작 (백그라운드 스레드). 한 번만 호출."""
        global _stream_thread
        if _stream_thread is not None and _stream_thread.is_alive():
            return
        _stream_stop.clear()
        _stream_thread = threading.Thread(target=_run_btc_stream, daemon=True)
        _stream_thread.start()
        logger.info("BTC 실시간 시세 스트림 시작")

    def stop_stream(self):
        """스트림 종료."""
        _stream_stop.set()
        if _stream_thread is not None:
            _stream_thread.join(timeout=3)

    def get_current_price(self):
        """
        현재 BTC/USD 가격 반환.
        SSE 스트림이 켜져 있고 최근 값이 있으면 캐시 사용, 아니면 REST 한 번 호출.
        """
        global _stream_price, _stream_updated
        now = time.time()
        if _stream_price is not None and (now - _stream_updated) <= STREAM_PRICE_MAX_AGE:
            return _stream_price
        return self._fetch_via_rest()

    def get_price_at_timestamp(self, timestamp_sec: int) -> float | None:
        """
        특정 Unix 시각(초)의 BTC 가격을 Pyth Benchmarks API로 조회. 같은 구간은 캐시해 두고 재호출 안 함.
        Opinion 토픽 시작 시각에 쓰면 됨.
        """
        ts = int(timestamp_sec)
        if ts <= 0:
            return None
        if ts in _price_at_ts_cache:
            return _price_at_ts_cache[ts]
        try:
            url = f"{PYTH_BENCHMARKS_URL}/v1/updates/price/{ts}"
            params = {"ids": [self.feed_id], "parsed": True}
            # ids는 배열이라 requests는 ids=0x... 형태로 보냄
            resp = requests.get(url, params={"ids": self.feed_id, "parsed": "true"}, timeout=15)
            if resp.status_code == 404:
                logger.warning("Pyth Benchmarks: 해당 시각(%s) 가격 없음", ts)
                return None
            resp.raise_for_status()
            data = resp.json()
            parsed = data.get("parsed")
            if isinstance(parsed, list) and parsed:
                price_info = parsed[0].get("price") or {}
            elif isinstance(parsed, dict):
                price_info = parsed.get("price") or {}
            else:
                return None
            p = int(price_info.get("price", 0))
            expo = int(price_info.get("expo", 0))
            price = float(p * (10 ** expo))
            if price > 0:
                _price_at_ts_cache[ts] = price
                logger.info("BTC 가격(시점 %s): $%s", ts, f"{price:,.2f}")
                return price
        except requests.exceptions.RequestException as e:
            logger.warning("Pyth Benchmarks 조회 실패 (ts=%s): %s", ts, e)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Pyth Benchmarks 파싱 실패 (ts=%s): %s", ts, e)
        return None

    def _fetch_via_rest(self):
        """REST API로 한 번 조회 (Pyth latest_price_feeds)."""
        try:
            params = {"ids[]": self.feed_id}
            response = requests.get(self.api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data or len(data) == 0:
                raise ValueError("No price data returned from Pyth")
            price_feed = data[0]
            price_data = price_feed.get("price", {})
            price = int(price_data.get("price", 0))
            expo = int(price_data.get("expo", 0))
            btc_price = price * (10 ** expo)
            logger.info("BTC 가격(REST): $%s", f"{btc_price:,.2f}")
            return btc_price
        except requests.exceptions.RequestException as e:
            logger.error("BTC 가격 REST 실패: %s", e)
            raise
        except (KeyError, IndexError, ValueError) as e:
            logger.error("BTC 가격 파싱 실패: %s", e)
            raise

    def get_price_gap(self, start_price):
        """현재가 - start_price (갭)."""
        current_price = self.get_current_price()
        gap = current_price - start_price
        logger.info(
            "Price Gap: $%+.2f (Start: $%s → Current: $%s)",
            gap,
            f"{start_price:,.2f}",
            f"{current_price:,.2f}",
        )
        return gap


# Singleton
btc_price_service = BTCPriceService()
