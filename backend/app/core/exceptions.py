"""统一异常定义，见 CLAUDE.md 目录结构"""
from fastapi import HTTPException
from app.schemas.response import ErrorCode


class AppException(HTTPException):
    """业务异常基类，自动映射到统一响应结构"""

    def __init__(self, error_code: int, message: str) -> None:
        # HTTP 状态码映射：4xxx → 400/401/403/404，5xxx → 500/502
        if 4100 <= error_code <= 4199:
            http_status = 401
        elif 4200 <= error_code <= 4299:
            http_status = 422
        elif error_code == ErrorCode.FORBIDDEN:
            http_status = 403
        elif 4000 <= error_code <= 4099:
            http_status = 400
        else:
            http_status = 500
        super().__init__(status_code=http_status, detail={"code": error_code, "message": message})
        self.error_code = error_code
        self.error_message = message
