"""信息模块管理：模块元数据 + 属性字段定义。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import AppError, NotFound, ok, page_ok
from app.db.session import get_db
from app.models.info import GEOM_TYPES, Feature, InfoField, InfoModule
from app.models.system import User
from app.schemas.common import PageParams
from app.schemas.info import FieldOut, ModuleOut, ModuleUpsert
from app.services.audit import log_action

router = APIRouter(prefix="/modules", tags=["信息模块"])

guard_view = require_permissions("module:view", "feature:view")
guard_write = require_permissions("module:create", "module:update", "module:delete")

GEOM_TYPE_LABEL = {"point": "点", "line": "线", "polygon": "面"}


def to_module_out(module: InfoModule, feature_count: int | None = None) -> dict:
    return ModuleOut(
        id=module.id,
        code=module.code,
        name=module.name,
        geom_type=module.geom_type,
        category=module.category,
        color=module.color,
        icon=module.icon,
        layer_order=module.layer_order,
        editable=module.editable,
        is_active=module.is_active,
        description=module.description,
        created_at=module.created_at,
        updated_at=module.updated_at,
        fields=[FieldOut.model_validate(f).model_dump() for f in module.fields],
        feature_count=feature_count,
    ).model_dump()


def count_map(db: Session) -> dict[int, int]:
    rows = (
        db.query(Feature.module_id, func.count(Feature.id))
        .group_by(Feature.module_id)
        .all()
    )
    return dict(rows)


@router.get("", summary="信息模块列表")
def list_modules(
    pg: PageParams = Depends(),
    geom_type: str | None = None,
    category: str | None = None,
    is_active: bool | None = None,
    with_count: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(InfoModule)
    if pg.keyword:
        like = f"%{pg.keyword}%"
        q = q.filter(InfoModule.name.ilike(like) | InfoModule.code.ilike(like))
    if geom_type:
        if geom_type not in GEOM_TYPES:
            raise AppError(f"geom_type 需为 {'/'.join(GEOM_TYPES)}")
        q = q.filter(InfoModule.geom_type == geom_type)
    if category:
        q = q.filter(InfoModule.category == category)
    if is_active is not None:
        q = q.filter(InfoModule.is_active == is_active)

    total = q.count()
    rows = (
        q.order_by(InfoModule.layer_order, InfoModule.id)
        .offset(pg.offset)
        .limit(pg.page_size)
        .all()
    )
    counts = count_map(db) if with_count else {}
    return page_ok(
        [to_module_out(m, counts.get(m.id, 0)) for m in rows],
        total,
        pg.page,
        pg.page_size,
    )


@router.get("/brief", summary="精简模块列表（图层面板用）")
def brief_modules(
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    rows = (
        db.query(InfoModule)
        .filter(InfoModule.is_active.is_(True))
        .order_by(InfoModule.layer_order, InfoModule.id)
        .all()
    )
    return ok(
        [
            {
                "id": m.id,
                "code": m.code,
                "name": m.name,
                "geom_type": m.geom_type,
                "geom_type_label": GEOM_TYPE_LABEL.get(m.geom_type, m.geom_type),
                "color": m.color,
                "layer_order": m.layer_order,
                "field_count": len(m.fields),
            }
            for m in rows
        ]
    )


@router.get("/geom-types", summary="支持的空间信息类型")
def geom_types(_: User = Depends(guard_view)):
    return ok(
        [
            {"value": t, "label": GEOM_TYPE_LABEL[t], "geojson_types": list()}
            for t in GEOM_TYPES
        ]
    )


@router.get("/{module_id}", summary="信息模块详情")
def get_module(
    module_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    module = db.get(InfoModule, module_id)
    if module is None:
        raise NotFound("信息模块不存在")
    return ok(to_module_out(module, count_map(db).get(module.id, 0)))


def _validate_fields(fields):
    keys = [f.key for f in fields]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        raise AppError(f"属性字段编码重复：{', '.join(sorted(dup))}")
    for f in fields:
        if f.data_type in ("select", "multiselect") and not f.options:
            raise AppError(f"字段「{f.label}」为下拉类型，必须配置选项 options")


def _apply_fields(module: InfoModule, payload_fields) -> None:
    existing = {f.id: f for f in module.fields}
    keep_ids = set()
    for item in payload_fields:
        if item.id and item.id in existing:
            field = existing[item.id]
            keep_ids.add(item.id)
        else:
            field = InfoField(module=module)
            module.fields.append(field)
        for attr in (
            "key", "label", "data_type", "required", "unique_value", "options",
            "default_value", "placeholder", "help_text", "validation",
            "show_in_list", "searchable", "sort_order",
        ):
            setattr(field, attr, getattr(item, attr))
    for field_id, field in existing.items():
        if field_id not in keep_ids:
            module.fields.remove(field)


@router.post("", summary="新增信息模块")
def create_module(
    payload: ModuleUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    if db.query(InfoModule).filter(InfoModule.code == payload.code).first():
        raise AppError(f"模块编码 {payload.code} 已存在")
    _validate_fields(payload.fields)

    module = InfoModule(
        code=payload.code,
        name=payload.name,
        geom_type=payload.geom_type,
        category=payload.category,
        color=payload.color,
        icon=payload.icon,
        layer_order=payload.layer_order,
        editable=payload.editable,
        is_active=payload.is_active,
        description=payload.description,
        created_by=operator.id,
    )
    _apply_fields(module, payload.fields)
    db.add(module)
    db.flush()
    log_action(
        db,
        operator,
        "module:create",
        target=module.code,
        detail={"geom_type": module.geom_type, "fields": len(module.fields)},
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(module)
    return ok(to_module_out(module, 0), "信息模块已创建，可开始采集该模块数据")


@router.put("/{module_id}", summary="编辑信息模块（含字段整体覆盖）")
def update_module(
    module_id: int,
    payload: ModuleUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    module = db.get(InfoModule, module_id)
    if module is None:
        raise NotFound("信息模块不存在")
    dup = (
        db.query(InfoModule)
        .filter(InfoModule.code == payload.code, InfoModule.id != module_id)
        .first()
    )
    if dup:
        raise AppError(f"模块编码 {payload.code} 已存在")
    _validate_fields(payload.fields)

    used = db.query(func.count(Feature.id)).filter(Feature.module_id == module_id).scalar()
    if payload.geom_type != module.geom_type and used:
        raise AppError(f"该模块已采集 {used} 条数据，不能变更空间信息类型")

    module.code = payload.code
    module.name = payload.name
    module.geom_type = payload.geom_type
    module.category = payload.category
    module.color = payload.color
    module.icon = payload.icon
    module.layer_order = payload.layer_order
    module.editable = payload.editable
    module.is_active = payload.is_active
    module.description = payload.description
    _apply_fields(module, payload.fields)

    db.add(module)
    log_action(
        db, operator, "module:update", target=module.code,
        detail={"fields": len(module.fields)}, ip=client_ip(request),
    )
    db.commit()
    db.refresh(module)
    return ok(to_module_out(module, used), "信息模块已更新")


@router.delete("/{module_id}", summary="删除信息模块（连同采集数据）")
def delete_module(
    module_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    module = db.get(InfoModule, module_id)
    if module is None:
        raise NotFound("信息模块不存在")
    used = db.query(func.count(Feature.id)).filter(Feature.module_id == module_id).scalar()
    log_action(
        db, operator, "module:delete", target=module.code,
        detail={"feature_count": used}, ip=client_ip(request),
    )
    db.delete(module)
    db.commit()
    return ok({"deleted_features": used}, "信息模块已删除")
