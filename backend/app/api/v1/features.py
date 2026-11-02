"""采集要素：空间信息 + 属性信息。"""
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from geoalchemy2 import Geography
from sqlalchemy import func
from sqlalchemy import cast
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import AppError, Forbidden, NotFound, ok, page_ok
from app.db.session import get_db
from app.models.info import Feature, InfoModule
from app.models.system import User
from app.schemas.common import IdsPayload, PageParams
from app.schemas.info import FeatureMapOut, FeatureOut, FeatureUpdate, FeatureUpsert
from app.services import geom as geom_svc
from app.services.audit import log_action

router = APIRouter(prefix="/features", tags=["数据采集"])

guard_view = require_permissions("feature:view")
guard_write = require_permissions("feature:create", "feature:update", "feature:delete")


def _geo_cast(col):
    """geometry -> geography 并保持与业务一致的 SRID（用于面积/长度计算）。"""
    return cast(col, Geography(geometry_type="GEOMETRY", srid=settings.spatial_srid))


def _geom_exprs():
    return (
        func.ST_AsGeoJSON(Feature.geometry).label("geometry_json"),
        func.ST_AsGeoJSON(func.ST_Centroid(Feature.geometry)).label("center_json"),
        func.ST_Area(_geo_cast(Feature.geometry)).label("area_m2"),
        func.ST_Length(_geo_cast(Feature.geometry)).label("length_m"),
    )


def _build_out(
    feature: Feature,
    geometry_json: str | None,
    center_json: str | None,
    area_m2: float | None,
    length_m: float | None,
) -> dict:
    geometry = geom_svc.loads_geojson(geometry_json)
    center = geom_svc.loads_geojson(center_json)
    lng = lat = None
    if center and center.get("type") == "Point":
        lng, lat = center["coordinates"][0], center["coordinates"][1]
    return FeatureOut(
        id=feature.id,
        module_id=feature.module_id,
        module_name=feature.module.name if feature.module else None,
        code=feature.code,
        name=feature.name,
        geometry=geometry,
        properties=feature.properties,
        declared_lng=feature.declared_lng,
        declared_lat=feature.declared_lat,
        center_lng=lng,
        center_lat=lat,
        area_m2=round(area_m2, 2) if area_m2 else None,
        length_m=round(length_m, 2) if length_m else None,
        status=feature.status,
        remark=feature.remark,
        created_at=feature.created_at,
        updated_at=feature.updated_at,
    ).model_dump()


def _validate_properties(
    db: Session, module: InfoModule, properties: dict, feature_id: int | None = None
) -> dict:
    if not isinstance(properties, dict):
        raise AppError("属性信息必须是键值对象")
    known = {f.key: f for f in module.fields}
    cleaned: dict[str, Any] = {}
    for field in module.fields:
        value = properties.get(field.key, None)
        empty = value is None or value == "" or value == []
        if field.required and empty:
            raise AppError(f"属性「{field.label}」为必填项")
        if not empty and field.data_type in ("number", "integer"):
            try:
                cleaned[field.key] = int(value) if field.data_type == "integer" else float(value)
                continue
            except (TypeError, ValueError):
                raise AppError(f"属性「{field.label}」必须是数字")
        if not empty and field.data_type == "boolean":
            cleaned[field.key] = bool(value)
            continue
        if field.unique_value and not empty:
            q = db.query(Feature).filter(
                Feature.module_id == module.id,
                Feature.properties.op("->>")(field.key) == str(value),
            )
            if feature_id:
                q = q.filter(Feature.id != feature_id)
            if q.first():
                raise AppError(f"属性「{field.label}」的值 {value} 已存在")
        if not empty:
            cleaned[field.key] = value
    unknown = set(properties) - set(known)
    for key in unknown:
        cleaned[key] = properties[key]
    return cleaned


@router.get("", summary="采集数据列表")
def list_features(
    pg: PageParams = Depends(),
    module_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(Feature, *_geom_exprs())
    if module_id:
        q = q.filter(Feature.module_id == module_id)
    if status:
        q = q.filter(Feature.status == status)
    if pg.keyword:
        like = f"%{pg.keyword}%"
        q = q.filter(Feature.name.ilike(like) | Feature.code.ilike(like))

    count_q = db.query(func.count(Feature.id))
    if module_id:
        count_q = count_q.filter(Feature.module_id == module_id)
    if status:
        count_q = count_q.filter(Feature.status == status)
    if pg.keyword:
        like = f"%{pg.keyword}%"
        count_q = count_q.filter(Feature.name.ilike(like) | Feature.code.ilike(like))
    total = count_q.scalar() or 0

    rows = q.order_by(Feature.id.desc()).offset(pg.offset).limit(pg.page_size).all()
    return page_ok(
        [_build_out(f, gj, cj, area, length) for f, gj, cj, area, length in rows],
        total,
        pg.page,
        pg.page_size,
    )


@router.get("/stats", summary="各模块采集量统计")
def stats(db: Session = Depends(get_db), _: User = Depends(guard_view)):
    rows = (
        db.query(InfoModule.id, InfoModule.name, InfoModule.geom_type, InfoModule.color,
                 func.count(Feature.id))
        .outerjoin(Feature, Feature.module_id == InfoModule.id)
        .group_by(InfoModule.id, InfoModule.name, InfoModule.geom_type, InfoModule.color)
        .order_by(InfoModule.layer_order, InfoModule.id)
        .all()
    )
    return ok(
        {
            "modules": [
                {
                    "id": r[0], "name": r[1], "geom_type": r[2], "color": r[3],
                    "count": r[4],
                }
                for r in rows
            ],
            "total_features": sum(r[4] for r in rows),
            "total_modules": len(rows),
        }
    )


@router.get("/map", summary="地图渲染数据（按模块聚合）")
def map_features(
    module_ids: str | None = Query(None, description="逗号分隔的模块 id"),
    limit: int = Query(2000, ge=1, le=20000),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(Feature, *_geom_exprs())
    if module_ids:
        ids = [int(i) for i in module_ids.split(",") if i.strip().isdigit()]
        if ids:
            q = q.filter(Feature.module_id.in_(ids))
    rows = q.order_by(Feature.id).limit(limit).all()

    grouped: dict[int, dict] = {}
    for f, gj, cj, area, length in rows:
        bucket = grouped.setdefault(
            f.module_id,
            {
                "module_id": f.module_id,
                "module_name": f.module.name if f.module else None,
                "geom_type": f.module.geom_type if f.module else None,
                "color": f.module.color if f.module else "#2d8cf0",
                "features": [],
            },
        )
        bucket["features"].append(
            FeatureMapOut(
                id=f.id,
                module_id=f.module_id,
                code=f.code,
                name=f.name,
                geometry=geom_svc.loads_geojson(gj),
                properties={
                    "id": f.id,
                    "name": f.name,
                    "code": f.code,
                    "status": f.status,
                    **(f.properties or {}),
                },
            ).model_dump()
        )
    return ok(list(grouped.values()))


@router.get("/{feature_id}", summary="采集数据详情")
def get_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    row = (
        db.query(Feature, *_geom_exprs()).filter(Feature.id == feature_id).one_or_none()
    )
    if row is None:
        raise NotFound("采集数据不存在")
    f, gj, cj, area, length = row
    return ok(_build_out(f, gj, cj, area, length))


@router.post("", summary="新增采集数据（空间+属性）")
def create_feature(
    payload: FeatureUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    module = db.get(InfoModule, payload.module_id)
    if module is None:
        raise NotFound("信息模块不存在")
    if not module.is_active:
        raise AppError(f"信息模块「{module.name}」已停用")

    # 先校验几何类型与拓扑，再校验属性（类型不符时优先给空间错误提示）
    ewkb = geom_svc.to_wkb_hex(payload.geometry, module.geom_type)
    properties = _validate_properties(db, module, payload.properties or {})

    code = payload.code or geom_svc.generate_code(module, db)
    if db.query(Feature).filter(Feature.code == code).first():
        raise AppError(f"数据编号 {code} 已存在")

    feature = Feature(
        module_id=module.id,
        code=code,
        name=payload.name or properties.get("name") or module.name,
        geometry=ewkb,
        properties=properties,
        declared_lng=payload.declared_lng,
        declared_lat=payload.declared_lat,
        status=payload.status,
        remark=payload.remark,
        created_by=operator.id,
        updated_by=operator.id,
    )
    db.add(feature)
    db.flush()
    log_action(
        db, operator, "feature:create", target=code,
        detail={"module": module.code}, ip=client_ip(request),
    )
    db.commit()
    db.refresh(feature)
    row = db.query(Feature, *_geom_exprs()).filter(Feature.id == feature.id).one()
    return ok(_build_out(*row), "采集数据已保存")


@router.put("/{feature_id}", summary="编辑采集数据")
def update_feature(
    feature_id: int,
    payload: FeatureUpdate,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise NotFound("采集数据不存在")
    module = db.get(InfoModule, feature.module_id)
    if module and not module.editable:
        raise Forbidden("该信息模块已锁定，不允许编辑")

    data = payload.model_dump(exclude_unset=True)
    if "properties" in data and data["properties"] is not None:
        merged = {**(feature.properties or {}), **data["properties"]}
        feature.properties = _validate_properties(db, module, merged, feature_id)
    if data.get("geometry") is not None:
        feature.geometry = geom_svc.to_wkb_hex(data["geometry"], module.geom_type)
    for key in ("name", "code", "declared_lng", "declared_lat", "status", "remark"):
        if key in data:
            setattr(feature, key, data[key])
    feature.updated_by = operator.id

    db.add(feature)
    log_action(db, operator, "feature:update", target=feature.code, ip=client_ip(request))
    db.commit()
    db.refresh(feature)
    row = db.query(Feature, *_geom_exprs()).filter(Feature.id == feature_id).one()
    return ok(_build_out(*row), "采集数据已更新")


@router.delete("/{feature_id}", summary="删除采集数据")
def delete_feature(
    feature_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise NotFound("采集数据不存在")
    log_action(db, operator, "feature:delete", target=feature.code, ip=client_ip(request))
    db.delete(feature)
    db.commit()
    return ok(None, "采集数据已删除")


@router.post("/batch-delete", summary="批量删除采集数据")
def batch_delete(
    payload: IdsPayload,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    deleted = (
        db.query(Feature).filter(Feature.id.in_(payload.ids)).delete(synchronize_session=False)
    )
    log_action(
        db, operator, "feature:batch_delete",
        detail={"count": deleted, "ids": payload.ids}, ip=client_ip(request),
    )
    db.commit()
    return ok({"deleted": deleted}, f"已删除 {deleted} 条")


@router.get("/template/{module_id}", summary="按模块生成空白属性表单默认值")
def blank_properties(
    module_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    module = db.get(InfoModule, module_id)
    if module is None:
        raise NotFound("信息模块不存在")
    defaults = {}
    for field in module.fields:
        if field.default_value not in (None, ""):
            defaults[field.key] = (
                float(field.default_value)
                if field.data_type in ("number", "integer")
                else field.default_value
            )
    return ok({"properties": defaults, "geom_type": module.geom_type, "module": module.code})
