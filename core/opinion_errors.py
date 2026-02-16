"""
Opinion.trade API 에러 해석 규칙
- 400이 아닌 에러 코드(401, 404, 429, 500 등)가 오면 원문을 UI에 그대로 보이지 않고
  해석해 저장한 뒤, 사용자가 이해할 수 있는 에러 메시지로 표시한다.
"""
from typing import Optional

# Opinion OpenAPI 응답 code → 사용자용 한글 메시지 (docs/OPINION_OPENAPI.md §6 기준)
OPINION_API_CODE_MESSAGES = {
    0: None,  # 성공
    400: "요청 형식이 잘못되었습니다. 파라미터를 확인해 주세요.",
    401: "API 키 인증에 실패했습니다. .env의 OPINION_API_KEY가 올바른지, 해당 지갑과 세트로 발급된 키인지 확인해 주세요.",
    404: "요청한 시장 또는 자원을 찾을 수 없습니다.",
    429: "요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요. (초당 15회 제한)",
    500: "Opinion 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}

# HTTP status_code → 사용자용 메시지 (API 프록시/네트워크 단)
HTTP_STATUS_MESSAGES = {
    400: "잘못된 요청입니다.",
    401: "인증이 필요합니다. 로그인 또는 API 키를 확인해 주세요.",
    403: "접근 권한이 없습니다.",
    404: "요청한 항목을 찾을 수 없습니다.",
    429: "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    500: "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    502: "Opinion 서버에 연결할 수 없습니다. 네트워크 또는 프록시를 확인해 주세요.",
    503: "서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
}

# 자동 Go! / 수동 실행 시 사전 조건 실패 코드 → 사용자용 메시지
AUTO_ERROR_CODES = {
    "NO_API_KEY": "API 키가 설정되지 않았습니다. .env에 OPINION_API_KEY를 넣어 주세요.",
    "NO_PROXY": "프록시가 설정되지 않았습니다. .env에 OPINION_PROXY를 넣어 주세요.",
    "NEED_TWO_ACCOUNTS": "자동/수동 거래에는 최소 2개의 계정이 필요합니다. 계정 로그인을 먼저 해 주세요.",
    "NO_MARKET": "진행 중인 1시간 마켓을 찾을 수 없습니다. 잠시 후 다시 시도하거나 '불러오기'를 눌러 주세요.",
    "CLOB_NOT_READY": "주문 기능(CLOB SDK)이 아직 연동되지 않았습니다. API 키 발급 후 opinion-clob-sdk 연동이 필요합니다. 당분간 '수동 Go!'로 진행해 주세요.",
    "ALREADY_RUNNING": "자동 거래가 이미 실행 중입니다.",
    "START_PRICE_FAILED": "구간 시작 시각의 BTC 가격을 Pyth에서 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    "TRADE_NOT_READY": "현재 거래 조건이 충족되지 않았습니다. (호가창 또는 시장 상태 확인)",
    "UNKNOWN": "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}


def interpret_opinion_api_response(
    status_code: int,
    body: Optional[dict] = None,
    context: str = "",
) -> dict:
    """
    Opinion API 응답을 해석해 사용자용 메시지를 반환.
    - 400이 아닌 에러 코드면 원문(code/msg)은 로그용으로 두고, user_message를 UI에 표시할 값으로 쓴다.
    Returns:
        { "user_message": str, "error_code": int|str, "raw_message": str|None }
    """
    body = body or {}
    code = body.get("code") if isinstance(body, dict) else None
    raw_msg = body.get("msg") or body.get("message") or body.get("error") or ""
    if isinstance(raw_msg, dict):
        raw_msg = raw_msg.get("message") or str(raw_msg)

    # Opinion 응답 body에 code가 있으면 그걸 우선 해석
    if code is not None and code != 0:
        user_msg = OPINION_API_CODE_MESSAGES.get(int(code))
        if user_msg:
            return {
                "user_message": user_msg,
                "error_code": int(code),
                "raw_message": raw_msg or None,
            }
        user_msg = f"Opinion API 오류 (code={code}). {raw_msg or '잠시 후 다시 시도해 주세요.'}"
        return {"user_message": user_msg, "error_code": code, "raw_message": raw_msg or None}

    # HTTP status만 있는 경우
    user_msg = HTTP_STATUS_MESSAGES.get(status_code)
    if user_msg:
        if context:
            user_msg = f"{context}: {user_msg}"
        return {
            "user_message": user_msg,
            "error_code": status_code,
            "raw_message": raw_msg or None,
        }
    user_msg = raw_msg or f"오류가 발생했습니다. (HTTP {status_code})"
    return {"user_message": user_msg, "error_code": status_code, "raw_message": raw_msg or None}


def get_auto_error_message(error_code: str) -> str:
    """자동 Go! 등 사전 조건 실패 시 사용자용 메시지."""
    return AUTO_ERROR_CODES.get(error_code, AUTO_ERROR_CODES["UNKNOWN"])
