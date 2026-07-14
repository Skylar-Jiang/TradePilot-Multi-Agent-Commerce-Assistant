from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.schemas.common import ApiResponse, ResponseMeta

API_ERROR_RESPONSES: dict[int, dict[str, object]] = {
    status: {"model": ApiResponse[None], "description": "Unified TradePilot error envelope"}
    for status in (400, 404, 422, 503)
}


def success(
    request: Request,
    data: Any,
    *,
    status_code: int = 200,
    data_mode: str | None = None,
) -> ApiResponse[Any]:
    del status_code
    return ApiResponse[Any](
        success=True,
        data=data,
        meta=ResponseMeta(request_id=request.state.request_id, data_mode=data_mode),
        error=None,
    )


def failure(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "meta": {"request_id": request.state.request_id, "api_version": "v1", "data_mode": None},
            "error": {"code": code, "message": message, "details": details or []},
        },
    )
