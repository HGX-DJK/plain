"""用户管理。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, selectinload

from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import AppError, NotFound, ok, page_ok
from app.db.session import get_db
from app.models.system import Role, User
from app.schemas.common import PageParams
from app.schemas.system import UserCreate, UserInfoOut, UserUpdate
from app.api.v1.auth import build_user_info
from app.core.security import hash_password
from app.services.audit import log_action

router = APIRouter(prefix="/users", tags=["系统设置-用户"])

guard_view = require_permissions("system:view")
guard_user = require_permissions("system:user")


@router.get("", summary="用户列表")
def list_users(
    pg: PageParams = Depends(),
    role_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(User).options(selectinload(User.roles))
    if pg.keyword:
        like = f"%{pg.keyword}%"
        q = q.filter(
            User.username.ilike(like) | User.real_name.ilike(like) | User.dept.ilike(like)
        )
    if role_id:
        q = q.join(User.roles).filter(Role.id == role_id)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)

    total = q.count()
    rows = q.order_by(User.id).offset(pg.offset).limit(pg.page_size).all()
    return page_ok(
        [
            UserInfoOut(
                id=u.id,
                username=u.username,
                real_name=u.real_name,
                phone=u.phone,
                email=u.email,
                dept=u.dept,
                is_active=u.is_active,
                last_login_at=u.last_login_at,
                created_at=u.created_at,
                roles=[r.code for r in u.roles],
            ).model_dump()
            | {"role_names": [r.name for r in u.roles]}
            for u in rows
        ],
        total,
        pg.page,
        pg.page_size,
    )


@router.get("/{user_id}", summary="用户详情")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    return ok(build_user_info(user))


@router.post("", summary="新增用户")
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_user),
):
    if db.query(User).filter(User.username == payload.username).first():
        raise AppError(f"登录名 {payload.username} 已存在")
    roles = db.query(Role).filter(Role.id.in_(payload.role_ids)).all() if payload.role_ids else []
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        real_name=payload.real_name,
        phone=payload.phone,
        email=payload.email,
        dept=payload.dept,
        is_active=payload.is_active,
        remark=payload.remark,
        created_by=operator.id,
        roles=roles,
    )
    db.add(user)
    db.flush()
    log_action(db, operator, "user:create", target=user.username, ip=client_ip(request))
    db.commit()
    db.refresh(user)
    return ok(build_user_info(user), "用户已创建")


@router.put("/{user_id}", summary="编辑用户")
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_user),
):
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")

    data = payload.model_dump(exclude_unset=True)
    if "password" in data and data["password"]:
        user.password_hash = hash_password(data.pop("password"))
    else:
        data.pop("password", None)
    role_ids = data.pop("role_ids", None)
    for key, value in data.items():
        setattr(user, key, value)
    if role_ids is not None:
        user.roles = db.query(Role).filter(Role.id.in_(role_ids)).all()

    db.add(user)
    log_action(
        db,
        operator,
        "user:update",
        target=user.username,
        detail={"fields": list(data.keys())},
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return ok(build_user_info(user), "用户已更新")


@router.delete("/{user_id}", summary="删除用户")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_user),
):
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    if user.id == operator.id:
        raise AppError("不能删除当前登录账号")
    if any(r.code == "super_admin" for r in user.roles):
        raise AppError("不能删除超级管理员账号")

    log_action(db, operator, "user:delete", target=user.username, ip=client_ip(request))
    db.delete(user)
    db.commit()
    return ok(None, "用户已删除")


@router.post("/{user_id}/reset-password", summary="重置用户密码")
def reset_password(
    user_id: int,
    new_password: str,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_user),
):
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    if len(new_password) < 6:
        raise AppError("密码长度至少 6 位")
    user.password_hash = hash_password(new_password)
    db.add(user)
    log_action(db, operator, "user:reset_password", target=user.username, ip=client_ip(request))
    db.commit()
    return ok(None, "密码已重置")
