"""角色与权限配置。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import AppError, NotFound, ok
from app.db.session import get_db
from app.models.system import Permission, Role, User
from app.schemas.system import PermissionOut, RoleOut, RolePermissionsUpdate, RoleUpsert
from app.services.audit import log_action

router = APIRouter(tags=["系统设置-角色权限"])

guard_view = require_permissions("system:view")
guard_role = require_permissions("system:role")


def to_role_out(role: Role) -> dict:
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_builtin=role.is_builtin,
        created_at=role.created_at,
        permission_ids=[p.id for p in role.permissions],
    ).model_dump() | {"user_count": len(role.users), "permission_codes": [p.code for p in role.permissions]}


@router.get("/roles", summary="角色列表")
def list_roles(db: Session = Depends(get_db), _: User = Depends(guard_view)):
    roles = db.query(Role).options().order_by(Role.id).all()
    return ok([to_role_out(r) for r in roles])


@router.post("/roles", summary="新增角色")
def create_role(
    payload: RoleUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_role),
):
    if db.query(Role).filter(Role.code == payload.code).first():
        raise AppError(f"角色编码 {payload.code} 已存在")
    role = Role(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        permissions=db.query(Permission).filter(Permission.id.in_(payload.permission_ids)).all()
        if payload.permission_ids
        else [],
    )
    db.add(role)
    db.flush()
    log_action(db, operator, "role:create", target=role.code, ip=client_ip(request))
    db.commit()
    db.refresh(role)
    return ok(to_role_out(role), "角色已创建")


@router.put("/roles/{role_id}", summary="编辑角色")
def update_role(
    role_id: int,
    payload: RoleUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_role),
):
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("角色不存在")
    exist = db.query(Role).filter(Role.code == payload.code, Role.id != role_id).first()
    if exist:
        raise AppError(f"角色编码 {payload.code} 已存在")

    role.code = payload.code
    role.name = payload.name
    role.description = payload.description
    if payload.permission_ids:
        role.permissions = db.query(Permission).filter(
            Permission.id.in_(payload.permission_ids)
        ).all()
    db.add(role)
    log_action(db, operator, "role:update", target=role.code, ip=client_ip(request))
    db.commit()
    db.refresh(role)
    return ok(to_role_out(role), "角色已更新")


@router.put("/roles/{role_id}/permissions", summary="配置角色权限")
def set_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_role),
):
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("角色不存在")
    if role.code == "super_admin":
        raise AppError("超级管理员权限不可修改")
    role.permissions = db.query(Permission).filter(Permission.id.in_(payload.permission_ids)).all()
    db.add(role)
    log_action(
        db,
        operator,
        "role:set_permissions",
        target=role.code,
        detail={"count": len(payload.permission_ids)},
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(role)
    return ok(to_role_out(role), "权限已保存")


@router.delete("/roles/{role_id}", summary="删除角色")
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_role),
):
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("角色不存在")
    if role.is_builtin:
        raise AppError("内置角色不可删除")
    if role.users:
        raise AppError(f"仍有 {len(role.users)} 个用户属于该角色，请先调整用户角色")
    log_action(db, operator, "role:delete", target=role.code, ip=client_ip(request))
    db.delete(role)
    db.commit()
    return ok(None, "角色已删除")


@router.get("/permissions", summary="权限点列表")
def list_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
    perm_type: str | None = None,
):
    q = db.query(Permission)
    if perm_type:
        q = q.filter(Permission.perm_type == perm_type)
    rows = q.order_by(Permission.module, Permission.sort_order, Permission.id).all()
    return ok(
        [PermissionOut.model_validate(p).model_dump() for p in rows]
    )
