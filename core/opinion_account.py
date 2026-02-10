"""
Opinion 계정 관리: 디폴트 계정(EOA) + PK로 하나씩 로그인.
API 키는 해당 EOA(디폴트)에서만 사용하도록 매칭.
"""
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from eth_account import Account as EthAccount

from core.opinion_config import (
    OPINION_PROXY,
    OPINION_API_KEY,
    OPINION_DEFAULT_EOA,
    has_proxy,
)
from core.opinion_client import get_positions, get_trades

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OPINION_ACCOUNTS_JSON = DATA_DIR / "opinion_accounts.json"


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


class OpinionAccount:
    """단일 Opinion 계정 (EOA + 사용하는 API 키·프록시)."""

    def __init__(
        self,
        account_id: int,
        eoa: str,
        api_key: str,
        proxy: str,
        is_default: bool = False,
    ):
        self.id = account_id
        self.eoa = _normalize_eoa(eoa)
        self.api_key = api_key
        self.proxy = proxy
        self.is_default = is_default

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "eoa": self.eoa,
            "proxy_preview": self.proxy.split(":")[0] if self.proxy else "",
            "is_default": self.is_default,
        }


class OpinionAccountManager:
    """다중 계정 관리. 디폴트 1개 + PK 로그인으로 추가."""

    def __init__(self):
        self._accounts: List[OpinionAccount] = []
        self._load()

    def _load(self):
        """디폴트 계정 1개 + JSON에 저장된 계정 로드."""
        self._accounts = []
        # 디폴트 계정 (EOA만 있고 PK는 저장 안 함)
        if OPINION_DEFAULT_EOA and has_proxy():
            self._accounts.append(
                OpinionAccount(
                    account_id=1,
                    eoa=_normalize_eoa(OPINION_DEFAULT_EOA),
                    api_key=OPINION_API_KEY,
                    proxy=OPINION_PROXY.strip(),
                    is_default=True,
                )
            )
        if OPINION_ACCOUNTS_JSON.exists():
            try:
                with open(OPINION_ACCOUNTS_JSON) as f:
                    data = json.load(f)
                for item in data.get("accounts", []):
                    aid = int(item.get("id", 0))
                    if any(a.id == aid for a in self._accounts):
                        continue
                    self._accounts.append(
                        OpinionAccount(
                            account_id=aid,
                            eoa=_normalize_eoa(item["eoa"]),
                            api_key=item.get("api_key") or OPINION_API_KEY,
                            proxy=(item.get("proxy") or OPINION_PROXY or "").strip(),
                            is_default=bool(item.get("is_default")),
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
                "api_key": a.api_key,
                "proxy": a.proxy,
                "is_default": a.is_default,
            }
            for a in self._accounts
        ]
        with open(OPINION_ACCOUNTS_JSON, "w") as f:
            json.dump({"accounts": to_save}, f, indent=2)

    def get_all(self) -> List[OpinionAccount]:
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

    def login_with_pk(self, private_key: str) -> Dict[str, Any]:
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
        # API 키: 디폴트 EOA와 같을 때만 하드코딩 API 키 사용
        api_key = OPINION_API_KEY if eoa.lower() == _normalize_eoa(OPINION_DEFAULT_EOA).lower() else OPINION_API_KEY
        proxy = OPINION_PROXY.strip()
        # positions / trades 호출
        pos_res = get_positions(eoa, api_key, proxy)
        trade_res = get_trades(eoa, api_key, proxy)
        if not pos_res.get("ok") and not trade_res.get("ok"):
            err = pos_res.get("data") or trade_res.get("data") or {}
            msg = err.get("msg") or err.get("message") or pos_res.get("error") or "API 요청 실패"
            return {
                "success": False,
                "error": msg,
                "eoa": eoa,
                "code": "API_ERROR",
            }
        # 기존 계정에 있으면 그대로, 없으면 추가
        existing = self.get_by_eoa(eoa)
        if not existing:
            next_id = max([a.id for a in self._accounts], default=0) + 1
            new_acc = OpinionAccount(
                account_id=next_id,
                eoa=eoa,
                api_key=api_key,
                proxy=proxy,
                is_default=(eoa.lower() == _normalize_eoa(OPINION_DEFAULT_EOA).lower()),
            )
            self._accounts.append(new_acc)
            self._accounts.sort(key=lambda a: a.id)
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
