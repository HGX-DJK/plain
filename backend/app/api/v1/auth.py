"""登录、当前用户、修改密码。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, is_super_admin, permission_codes
from app.core.errors import AppError, ok
from app.core.permissions import ALL_PERMISSIONS
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.system import User
from app.schemas.system import LoginRequest, PasswordChange, UserInfoOut
from app.services.audit import log_action

router = APIRouter(tags=["鉴权"])


def build_user_info(user: User) -> dict:
    codes = (
        [p["code"] for p in ALL_PERMISSIONS]
        if is_super_admin(user)
        else sorted(permission_codes(user))
    )
    # roles / permissions 在模型里是字符串列表，不能直接 from_attributes 校验 ORM 关系
    return UserInfoOut(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        phone=user.phone,
        email=user.email,
        dept=user.dept,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        roles=[r.code for r in user.roles],
        permissions=codes,
    ).model_dump()


@router.post("/login", summary="账号密码登录")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError("用户名或密码错误", http_status=401)
    if not user.is_active:
        raise AppError("账号已停用，请联系管理员", http_status=403)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    log_action(db, user, "login", ip=client_ip(request))
    db.commit()

    token = create_access_token(user.id, user.username)
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "user": build_user_info(user),
        },
        "登录成功",
    )


@router.get("/me", summary="当前登录用户信息与权限")
def me(user: User = Depends(get_current_user)):
    return ok(build_user_info(user))


@router.post("/change-password", summary="修改自己的密码")
def change_password(
    payload: PasswordChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise AppError("原密码不正确")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    log_action(db, user, "change_password", target=user.username, ip=client_ip(request))
    db.commit()
    return ok(None, "密码已修改")


@router.post("/logout", summary="退出登录")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    log_action(db, user, "logout", ip=client_ip(request))
    db.commit()
    return ok(None, "已退出")
