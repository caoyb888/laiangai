from typing import TypeVar, Generic
from pydantic import BaseModel
import uuid

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    统一响应结构，见 CLAUDE.md §5.2
    所有接口必须返回此结构
    """
    code: int = 200
    message: str = "success"
    data: T | None = None
    request_id: str = ""

    @classmethod
    def ok(cls, data: T = None, message: str = "success") -> "ApiResponse[T]":
        return cls(code=200, message=message, data=data,
                   request_id=str(uuid.uuid4()))

    @classmethod
    def error(cls, code: int, message: str) -> "ApiResponse[None]":
        return cls(code=code, message=message, data=None,
                   request_id=str(uuid.uuid4()))


# 错误码常量，见 CLAUDE.md §5.2
class ErrorCode:
    # 参数错误
    INVALID_PARAM         = 4000
    FILE_TYPE_NOT_ALLOWED = 4001
    FILE_TOO_LARGE        = 4002
    # 认证错误
    UNAUTHORIZED          = 4100
    FORBIDDEN             = 4101
    TOKEN_EXPIRED         = 4102
    # 业务错误
    DOCUMENT_NOT_FOUND    = 4200
    TASK_NOT_FOUND        = 4201
    DOCUMENT_PARSE_FAILED = 4202
    DUPLICATE_FILE        = 4203
    # 系统错误
    INTERNAL_ERROR        = 5000
    # 外部服务错误
    LLM_API_ERROR         = 5100
    LLM_API_TIMEOUT       = 5101
    MINIO_ERROR           = 5102
