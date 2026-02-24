"""
BTC Price Module - 실시간 Bitcoin 시세 (Pyth Network)
- REST: 한 번 조회 (fallback)
- WebSocket: Pyth Hermes wss 연결로 실시간 수신, 캐시 갱신
"""
import asyncio
import json
import logging
import threading
import time

import requests

from config import Config

logger = logging.getLogger(__name__)

# WebSocket으로 받은 최신 가격 캐시 (스레드에서 갱신)
_stream_price: float | None = None
_stream_updated: float = 0.0
_stream_stop = threading.Event()
_stream_thread: threading.Thread | None = None

# 스트림 가격 유효 시간(초). 이 시간 지나면 get_current_price()가 REST로 fallback
STREAM_PRICE_MAX_AGE = 120

# 특정 시점 가격 캐시 (topic 구간당 1회만 Pyth Benchmarks 호출). key: start_ts(초), value: 가격
_price_at_ts_cache: dict[int, float] = {}
PYTH_BENCHMARKS_URL = "https://benchmarks.pyth.network"

# Pyth Hermes WebSocket
PYTH_HERMES_WS_URL = "wss://hermes.pyth.network/ws"
RECONNECT_DELAY = 5


def _parse_pyth_price_from_message(data: dict) -> float | None:
    """
    Pyth WS 'price_update' 또는 SSE 스타일 payload에서 BTC 가격 추출.
    - price_feed: { "parsed": [{ "price": { "price": int, "expo": int } }] }
    - 또는 parsed[0].price (price, expo)
    """
    try:
        # price_update 스타일
        price_feed = data.get("price_feed") or data.get("parsed")
        if price_feed is None and "parsed" in data:
            price_feed = data.get("parsed")
        if isinstance(price_feed, list) and price_feed:
            price_info = price_feed[0].get("price") or price_feed[0]
        elif isinstance(price_feed, dict):
            price_info = price_feed.get("price") or price_feed
        else:
            return None
        if isinstance(price_info, dict):
            p = int(price_info.get("price", 0))
            expo = int(price_info.get("expo", 0))
            return float(p * (10 ** expo))
        return None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


async def _btc_ws_loop(feed_id: str):
    """WebSocket 연결 유지 및 수신 루프. 끊기면 재연결."""
    global _stream_price, _stream_updated
    try:
        import websockets
    except ImportError:
        logger.warning("websockets 미설치. pip install websockets 후 재시작하면 실시간 시세가 동작합니다.")
        return
    while not _stream_stop.is_set():
        try:
            async with websockets.connect(
                PYTH_HERMES_WS_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                # 구독 메시지 전송
                await ws.send(json.dumps({"type": "subscribe", "ids": [feed_id]}))
                logger.info("BTC 실시간 시세 WebSocket 연결됨: %s", PYTH_HERMES_WS_URL)
                async for raw in ws:
                    if _stream_stop.is_set():
                        break
                    try:
                        data = json.loads(raw)
                        price = _parse_pyth_price_from_message(data)
                        if price is not None and price > 0:
                            _stream_price = price
                            _stream_updated = time.time()
                            logger.debug("BTC 시세 갱신: $%s", f"{price:,.2f}")
                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        logger.debug("BTC WS 메시지 파싱: %s", e)
        except Exception as e:
            if not _stream_stop.is_set():
                logger.warning("BTC WebSocket 연결 끊김: %s, %s초 후 재연결", e, RECONNECT_DELAY)
        if not _stream_stop.is_set():
            await asyncio.sleep(RECONNECT_DELAY)


def _run_btc_stream():
    """백그라운드: asyncio + WebSocket 루프 실행 (스레드 1개에서 이벤트 루프)."""
    feed_id = getattr(Config, "BTC_PRICE_FEED_ID", "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43")
    logger.info("BTC 실시간 시세 WebSocket 연결 중: %s", PYTH_HERMES_WS_URL)
    try:
        asyncio.run(_btc_ws_loop(feed_id))
    except Exception as e:
        logger.exception("BTC WebSocket 루프 종료: %s", e)


class BTCPriceService:
    """실시간 BTC/USD 시세 (Pyth Network REST + WebSocket 스트림)"""

    def __init__(self):
        self.api_url = Config.PYTH_API_URL
        self.feed_id = Config.BTC_PRICE_FEED_ID

    def start_stream(self):
        """Pyth Hermes WebSocket 스트림 시작 (백그라운드 스레드). 한 번만 호출."""
        global _stream_thread
        if _stream_thread is not None and _stream_thread.is_alive():
            return
        _stream_stop.clear()
        _stream_thread = threading.Thread(target=_run_btc_stream, daemon=True)
        _stream_thread.start()
        logger.info("BTC 실시간 시세 WebSocket 스트림 시작")

    def stop_stream(self):
        """스트림 종료."""
        _stream_stop.set()
        if _stream_thread is not None:
            _stream_thread.join(timeout=3)

    def get_current_price(self):
        """
        현재 BTC/USD 가격 반환.
        WebSocket 스트림이 켜져 있고 최근 값이 있으면 캐시 사용, 아니면 REST 한 번 호출.
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
