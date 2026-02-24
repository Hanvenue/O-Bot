"""
Opinion.trade - 설정 (.env에서 로드)
계정 N: OPINION_EOA_N, OPINION_API_KEY_N, OPINION_PROXY_N (N=1,2,3,...)
계정 1은 예전 이름 호환: OPINION_DEFAULT_EOA, OPINION_API_KEY, OPINION_PROXY (= _1 과 동일)
"""
import os
from pathlib import Path
from typing import List, Tuple, Optional

# 프로젝트 루트의 .env를 명시적으로 로드 (config 로드 순서와 무관하게 적용)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


# 예전 이름 호환 (계정 1)
OPINION_PROXY = _env("OPINION_PROXY") or _env("OPINION_PROXY_1")
OPINION_API_KEY = _env("OPINION_API_KEY") or _env("OPINION_API_KEY_1")
OPINION_DEFAULT_EOA = _env("OPINION_DEFAULT_EOA") or _env("OPINION_EOA_1")
OPINION_API_KEY_2 = _env("OPINION_API_KEY_2")
OPINION_PROXY_2 = _env("OPINION_PROXY_2") or _env("OPINION_PROXY2")
OPINION_EOA_2 = _env("OPINION_EOA_2")

# Opinion OpenAPI 베이스 URL
OPINION_API_BASE = "https://proxy.opinion.trade:8443/openapi"

# .env에서 정의된 계정 최대 개수 (확장 시 이 값만 넘지 않으면 됨)
MAX_ENV_ACCOUNTS = 20


def get_env_accounts() -> List[Tuple[int, str, str, str, bool]]:
    """
    .env에 정의된 계정 목록을 (account_id, eoa, api_key, proxy, is_default) 리스트로 반환.
    계정 1: OPINION_EOA_1 또는 OPINION_DEFAULT_EOA, API_KEY_1 또는 OPINION_API_KEY, PROXY_1 또는 OPINION_PROXY
    계정 2~N: OPINION_EOA_N, OPINION_API_KEY_N, OPINION_PROXY_N. EOA·API_KEY가 둘 다 있을 때만 포함.
    """
    out: List[Tuple[int, str, str, str, bool]] = []
    for i in range(1, MAX_ENV_ACCOUNTS + 1):
        if i == 1:
            eoa = _env("OPINION_EOA_1") or OPINION_DEFAULT_EOA
            api_key = _env("OPINION_API_KEY_1") or OPINION_API_KEY
            proxy = _env("OPINION_PROXY_1") or OPINION_PROXY
        else:
            eoa = _env(f"OPINION_EOA_{i}")
            api_key = _env(f"OPINION_API_KEY_{i}")
            proxy = _env(f"OPINION_PROXY_{i}") or _env(f"OPINION_PROXY{i}")
        if not eoa or not api_key:
            if i == 1:
                break  # 계정 1 없으면 기본 계정 없음 → 기존 동작 유지
            continue  # 계정 2~N: 빈 슬롯 건너뛰고 계속 탐색
        out.append((i, eoa, api_key, proxy, i == 1))
    return out


def get_proxy_dict(proxy_str: str):
    """
    프록시 문자열 → requests용 dict.
    지원 형식: IP:PORT:USER:PASS, USER:PASS@IP:PORT, IP:PORT(인증 없음).
    """
    s = (proxy_str or "").strip().strip('"\'')
    if not s or ":" not in s:
        return None
    # USER:PASS@IP:PORT
    if "@" in s:
        try:
            user_pass, host_port = s.split("@", 1)
            user_pass = user_pass.strip()
            host_port = host_port.strip()
            if ":" in user_pass and ":" in host_port:
                url = f"http://{user_pass}@{host_port}"
                return {"http": url, "https": url}
        except (ValueError, IndexError):
            pass
        return None
    parts = s.split(":")
    # IP:PORT (인증 없음, 2부분)
    if len(parts) == 2:
        ip, port = parts[0].strip(), parts[1].strip()
        if ip and port:
            url = f"http://{ip}:{port}"
            return {"http": url, "https": url}
        return None
    # IP:PORT:USER:PASS (정확히 4부분)
    if len(parts) != 4:
        return None
    ip, port, user, password = parts
    url = f"http://{user}:{password}@{ip}:{port}"
    return {"http": url, "https": url}


def has_proxy() -> bool:
    """프록시가 하나라도 설정되어 있으면 True (어떤 계정이든)."""
    for _, _, _, proxy, _ in get_env_accounts():
        if proxy:
            return True
    return False
