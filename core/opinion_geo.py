"""
프록시 IP → 국가 코드·깃발 이모지 (UI 표시용).
ip-api.com 무료 사용 (45 req/min). 결과 캐시로 반복 호출 최소화.
"""
import logging
import socket
from typing import Tuple, Optional

import requests

logger = logging.getLogger(__name__)

# IP → (country_code, flag_emoji) 캐시
_geo_cache: dict = {}
# 로컬/비공개 IP는 조회 스킵
_PRIVATE_PREFIXES = ("127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.", "192.168.")
_TIMEOUT = 2


def _is_private_ip(ip: str) -> bool:
    if not ip or not ip.strip():
        return True
    return any(ip.strip().startswith(p) for p in _PRIVATE_PREFIXES)


def _country_code_to_flag(cc: str) -> str:
    """ISO 3166-1 alpha-2 (US, KR) → 깃발 이모지."""
    if not cc or len(cc) != 2:
        return ""
    try:
        return "".join(chr(ord(c) + 127397) for c in cc.upper())
    except Exception:
        return ""


def get_country_for_ip(ip: str) -> Tuple[Optional[str], str]:
    """
    IP로 국가 코드와 깃발 이모지 반환.
    반환: (country_code 또는 None, flag_emoji). 실패 시 ("", "🌐").
    """
    ip = (ip or "").strip()
    if not ip or _is_private_ip(ip):
        return None, "🌐"
    if ip in _geo_cache:
        return _geo_cache[ip][0], _geo_cache[ip][1]
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "countryCode"},
            timeout=_TIMEOUT,
        )
        if r.ok:
            data = r.json()
            cc = (data.get("countryCode") or "").strip()[:2]
            flag = _country_code_to_flag(cc) if cc else "🌐"
            _geo_cache[ip] = (cc or None, flag)
            return (cc or None), flag
    except (requests.RequestException, socket.timeout, ValueError) as e:
        logger.debug("GeoIP lookup %s: %s", ip, e)
    _geo_cache[ip] = (None, "🌐")
    return None, "🌐"
