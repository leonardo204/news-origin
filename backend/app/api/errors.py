"""
# errors.py - RFC 7807 Problem Details API Error Handling
# Version: 0.1.0
# Description: 표준화된 에러 응답 (RFC 7807 Problem Details)
"""

from typing import Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class APIError(Exception):
    """RFC 7807 Problem Details 형식의 API 에러"""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_type: str = "error",
        title: Optional[str] = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_type = error_type
        self.title = title or _status_title(status_code)
        super().__init__(detail)


def _status_title(status_code: int) -> str:
    """HTTP 상태 코드에 대한 기본 타이틀 반환"""
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    return titles.get(status_code, "Error")


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """APIError 예외 핸들러 - RFC 7807 Problem Details 형식 반환"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": exc.error_type,
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """FastAPI 유효성 검사 에러 핸들러 - RFC 7807 형식으로 변환"""
    errors = exc.errors()
    # 첫 번째 에러의 메시지를 상세 설명으로 사용
    first_error = errors[0] if errors else {}
    detail = f"{first_error.get('loc', ['unknown'])[-1]}: {first_error.get('msg', '유효하지 않은 입력입니다.')}"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "type": "validation_error",
            "title": "Unprocessable Entity",
            "status": 422,
            "detail": detail,
            "errors": errors,  # 전체 에러 목록 포함 (디버깅용)
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """일반 예외 핸들러 - 개발 환경에서만 상세 메시지 노출"""
    from app.config import get_settings

    settings = get_settings()
    request_id = request.headers.get("X-Request-ID", "unknown")

    # 개발 환경에서는 예외 메시지 노출
    if settings.app_env == "development":
        detail = f"{exc.__class__.__name__}: {str(exc)}"
    else:
        detail = "서버 내부 오류가 발생했습니다."

    return JSONResponse(
        status_code=500,
        content={
            "type": "internal_error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": detail,
            "request_id": request_id,
        },
    )
