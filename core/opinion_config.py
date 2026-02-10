"""
Opinion.trade - 설정 (.env에서 로드)
"""
import os

# .env에서 불러옴. 없으면 빈 문자열 → UI에서 "프록시를 추가해 주세요" 알림
OPINION_PROXY = (os.getenv("OPINION_PROXY") or "").strip()
OPINION_API_KEY = (os.getenv("OPINION_API_KEY") or "").strip()
OPINION_DEFAULT_EOA = (os.getenv("OPINION_DEFAULT_EOA") or "").strip()

# Opinion OpenAPI 베이스 URL
OPINION_API_BASE = "https://proxy.opinion.trade:8443/openapi"


def get_proxy_dict(proxy_str: str):
    """프록시 문자열(IP:PORT:USER:PASS) → requests용 dict. 형식 오류 시 None."""
    if not proxy_str or ":" not in proxy_str:
        return None
    parts = proxy_str.strip().split(":")
    if len(parts) != 4:
        return None
    ip, port, user, password = parts
    url = f"http://{user}:{password}@{ip}:{port}"
    return {"http": url, "https": url}


def has_proxy() -> bool:
    """프록시가 설정되어 있으면 True."""
    return bool(OPINION_PROXY and OPINION_PROXY.strip())
