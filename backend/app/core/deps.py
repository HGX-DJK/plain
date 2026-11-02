"""FastAPI 依赖：当前用户、权限校验。"""
from collections.abc import Callable

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.system import User

bearer_scheme = HTTPBearer(auto_error=False)

SUPER_ADMIN_ROLE = "super_admin"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise Unauthorized("缺少访问令牌")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:  # pragma: no cover
        raise Unauthorized(f"令牌无效：{exc}") from exc
    if payload is None:
        raise Unauthorized()
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise Unauthorized("用户不存在")
    if not user.is_active:
        raise Forbidden("账号已停用，请联系管理员")
    return user


def permission_codes(user: User) -> set[str]:
    codes: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            codes.add(perm.code)
    return codes


def is_super_admin(user: User) -> bool:
    return any(role.code == SUPER_ADMIN_ROLE for role in user.roles)


def require_permissions(*required: str) -> Callable:
    """接口权限依赖：拥有任一给定权限码（或超级管理员）才放行。"""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if is_super_admin(user):
            return user
        owned = permission_codes(user)
        if not required or owned.intersection(required):
            return user
        raise Forbidden(f"缺少权限：{'/'.join(required)}")

    return dependency


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
