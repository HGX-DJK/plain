"""统一返回体与异常。

所有接口返回 {"code": 0, "message": "ok", "data": ...}，
业务异常抛 AppError，由全局 handler 转成同样的结构（HTTP 状态保持语义化）。
"""
from typing import Any

from fastapi import HTTPException, status


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: int = 1,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        data: Any = None,
    ):
        self.message = message
        self.code = code
        self.http_status = http_status
        self.data = data
        super().__init__(message)


class NotFound(AppError):
    def __init__(self, message: str = "记录不存在"):
        super().__init__(message, code=404, http_status=status.HTTP_404_NOT_FOUND)


class Forbidden(AppError):
    def __init__(self, message: str = "无权限执行该操作"):
        super().__init__(message, code=403, http_status=status.HTTP_403_FORBIDDEN)


class Unauthorized(AppError):
    def __init__(self, message: str = "登录状态已失效，请重新登录"):
        super().__init__(message, code=401, http_status=status.HTTP_401_UNAUTHORIZED)


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def page_ok(items: list, total: int, page: int, page_size: int) -> dict:
    return ok(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size else 0,
        }
    )


__all__ = [
    "AppError",
    "NotFound",
    "Forbidden",
    "Unauthorized",
    "ok",
    "page_ok",
    "HTTPException",
]
