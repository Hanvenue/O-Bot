"""
Opinion 계정 관리: 디폴트 계정(EOA) + PK로 하나씩 로그인.
API 키는 해당 EOA(디폴트)에서만 사용하도록 매칭.
"""
import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from eth_account import Account as EthAccount

from core.opinion_config import (
    OPINION_PROXY,
    OPINION_API_KEY,
    OPINION_DEFAULT_EOA,
    get_env_accounts,
    has_proxy,
)
from core.opinion_client import get_positions, get_trades
from core.opinion_geo import get_country_for_ip

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OPINION_ACCOUNTS_JSON = DATA_DIR / "opinion_accounts.json"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _ensure_env_loaded() -> None:
    """.env를 한 번 더 로드해 최신 값 반영 (로드 순서 이슈 회피)."""
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except Exception as e:
            logger.debug("_ensure_env_loaded: %s", e)


def _normalize_eoa(addr: str) -> str:
    a = (addr or "").strip()
    if a.startswith("0x"):
        return a
    return "0x" + a


def _eoa_from_pk(private_key: str) -> Optional[str]:
    """PK에서 EOA 주소만 추출. 실패 시 None."""
    pk = (private_key or "").strip()
    if not pk:
        return None
    try:
        acc = EthAccount.from_key(pk)
        return acc.address
    except Exception:
        return None


def _proxy_display_host(proxy_str: str) -> str:
    """
    프록시 문자열에서 IP/호스트만 추출 (UI 표시용).
    지원 형식: IP:PORT:USER:PASS, USER:PASS@IP:PORT, IP:PORT 등.
    """
    s = (proxy_str or "").strip().strip('"\'')
    if not s:
        return ""
    # USER:PASS@IP:PORT → @ 뒤 부분에서 호스트 추출
    if "@" in s:
        try:
            host_part = s.split("@")[-1].strip()
            return host_part.split(":")[0].strip() or ""
        except IndexError:
            pass
    # IP:PORT 또는 IP:PORT:USER:PASS → 첫 번째 세그먼트
    parts = s.split(":")
    for p in parts:
        p = p.strip().strip('"\'')
        if not p:
            continue
        if p.lower() in ("http", "https", "socks5"):
            continue
        return p
    return ""


class OpinionAccount:
    """단일 Opinion 계정 (EOA + 사용하는 API 키·프록시 + 이름)."""

    def __init__(
        self,
        account_id: int,
        eoa: str,
        api_key: str,
        proxy: str,
        is_default: bool = False,
        name: Optional[str] = None,
    ):
        self.id = account_id
        self.eoa = _normalize_eoa(eoa)
        self.api_key = api_key
        self.proxy = proxy
        self.is_default = is_default
        self.name = (name or "").strip() or None

    def to_dict(self) -> dict:
        proxy_ip = _proxy_display_host(self.proxy)
        _, flag_emoji = get_country_for_ip(proxy_ip)
        return {
            "id": self.id,
            "eoa": self.eoa,
            "name": self.name,
            "proxy_preview": proxy_ip or "—",
            "flag_emoji": flag_emoji,
            "is_default": self.is_default,
        }


class OpinionAccountManager:
    """다중 계정 관리. 디폴트 1개 + PK 로그인으로 추가."""

    def __init__(self):
        self._accounts: List[OpinionAccount] = []
        self._load()

    def _load(self):
        """.env에 정의된 계정(1,2,3,...) + JSON(PK 로그인)에서 로드."""
        self._accounts = []
        _ensure_env_loaded()
        for account_id, eoa, api_key, proxy, is_default in get_env_accounts():
            name = f"Wallet {account_id:02d}" if account_id <= 99 else f"Wallet {account_id}"
            self._accounts.append(
                OpinionAccount(
                    account_id=account_id,
                    eoa=_normalize_eoa(eoa),
                    api_key=api_key,
                    proxy=proxy,
                    is_default=is_default,
                    name=name,
                )
            )
        if OPINION_ACCOUNTS_JSON.exists():
            try:
                with open(OPINION_ACCOUNTS_JSON) as f:
                    data = json.load(f)
                for item in data.get("accounts", []):
                    aid = int(item.get("id", 0))
                    if any(a.id == aid for a in self._accounts):
                        continue  # .env에서 이미 로드한 1, 2는 건너뜀
                    self._accounts.append(
                        OpinionAccount(
                            account_id=aid,
                            eoa=_normalize_eoa(item["eoa"]),
                            api_key=item.get("api_key") or OPINION_API_KEY,
                            proxy=(item.get("proxy") or OPINION_PROXY or "").strip(),
                            is_default=bool(item.get("is_default")),
                            name=item.get("name"),
                        )
                    )
                self._accounts.sort(key=lambda a: a.id)
            except Exception as e:
                logger.warning("Failed to load opinion_accounts.json: %s", e)

    def _save(self):
        """디폴트 제외 나머지 계정만 JSON에 저장 (PK는 저장 안 함)."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        to_save = [
            {
                "id": a.id,
                "eoa": a.eoa,
                "name": a.name,
                "api_key": a.api_key,
                "proxy": a.proxy,
                "is_default": a.is_default,
            }
            for a in self._accounts
        ]
        with open(OPINION_ACCOUNTS_JSON, "w") as f:
            json.dump({"accounts": to_save}, f, indent=2)

    def get_all(self) -> List[OpinionAccount]:
        """목록 반환 전에 .env/JSON을 다시 읽어 계정 2 프록시 등 최신 반영."""
        self._load()
        return list(self._accounts)

    def get_by_id(self, account_id: int) -> Optional[OpinionAccount]:
        for a in self._accounts:
            if a.id == account_id:
                return a
        return None

    def get_by_eoa(self, eoa: str) -> Optional[OpinionAccount]:
        e = _normalize_eoa(eoa)
        for a in self._accounts:
            if a.eoa.lower() == e.lower():
                return a
        return None

    def login_with_pk(self, private_key: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        PK로 로그인 시도.
        - 프록시 없으면 에러 (프록시를 추가해 주세요)
        - EOA 도출 후, 디폴트 EOA와 같으면 디폴트 API키 사용.
        - positions + trades 호출해서 리턴값 전부 반환.
        """
        if not has_proxy():
            return {
                "success": False,
                "error": "프록시를 추가해 주세요.",
                "code": "NO_PROXY",
            }
        eoa = _eoa_from_pk(private_key)
        if not eoa:
            return {"success": False, "error": "유효한 지갑 Private Key가 아닙니다.", "code": "INVALID_PK"}
        eoa = _normalize_eoa(eoa)
        # API 키·프록시: EOA가 .env 어느 계정과 일치하는지 찾고, 없으면 계정 1 사용
        api_key, proxy = OPINION_API_KEY, OPINION_PROXY.strip()
        for _id, _eoa, _ak, _px, _ in get_env_accounts():
            if _eoa and _normalize_eoa(_eoa).lower() == eoa.lower():
                api_key, proxy = _ak, (_px or "").strip()
                break
        # positions / trades 호출 (문서: walletAddress는 지갑 주소, API 키는 apikey 헤더)
        pos_res = get_positions(eoa, api_key, proxy)
        trade_res = get_trades(eoa, api_key, proxy)
        if not pos_res.get("ok"):
            logger.warning("Opinion positions API failed: eoa=%s body=%s", eoa, pos_res.get("data"))
        if not trade_res.get("ok"):
            logger.warning("Opinion trades API failed: eoa=%s body=%s", eoa, trade_res.get("data"))
        if not pos_res.get("ok") and not trade_res.get("ok"):
            err_body = pos_res.get("data") or trade_res.get("data") or {}
            status = pos_res.get("status_code") or trade_res.get("status_code") or 500
            from core.opinion_errors import interpret_opinion_api_response
            interpreted = interpret_opinion_api_response(status, err_body, context="로그인")
            return {
                "success": False,
                "error": interpreted["user_message"],
                "eoa": eoa,
                "code": "API_ERROR",
                "api_code": err_body.get("code") if isinstance(err_body, dict) else status,
            }
        # 기존 계정에 있으면 이름만 갱신 가능, 없으면 추가
        nickname = (name or "").strip() or None
        existing = self.get_by_eoa(eoa)
        if not existing:
            next_id = max([a.id for a in self._accounts], default=0) + 1
            new_acc = OpinionAccount(
                account_id=next_id,
                eoa=eoa,
                api_key=api_key,
                proxy=proxy,
                is_default=(eoa.lower() == _normalize_eoa(OPINION_DEFAULT_EOA).lower()),
                name=nickname,
            )
            self._accounts.append(new_acc)
            self._accounts.sort(key=lambda a: a.id)
            self._save()
        else:
            if nickname:
                existing.name = nickname
                self._save()
        acc = existing or self.get_by_eoa(eoa)
        return {
            "success": True,
            "eoa": eoa,
            "account": acc.to_dict() if acc else {"eoa": eoa},
            "positions": pos_res.get("data"),
            "trades": trade_res.get("data"),
        }


opinion_account_manager = OpinionAccountManager()
