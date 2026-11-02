"""采集要素：空间信息 + 属性信息。"""
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from geoalchemy2 import Geography
from sqlalchemy import func
from sqlalchemy import cast
from sqlalchemy import text
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


# 地图取数：几何输出精度（度，6 位约等于 0.1m）与业务库 SRID
_GEOJSON_PRECISION = 6
_SRID = settings.spatial_srid


def _parse_module_ids(raw: str | None) -> list[int] | None:
    """逗号分隔的模块 id；None 表示不指定（由调用方按启用模块处理）。"""
    if raw is None or not raw.strip():
        return None
    return [int(i) for i in raw.split(",") if i.strip().isdigit()]


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    """解析视野包围盒并校验单位是否为「度」。

    地图投影若被误当成 Web 墨卡托（数值可达千万）传给 PostGIS，
    ST_MakeEnvelope 会直接报错或查不到数据，这里提前给出明确提示。
    """
    if raw is None or not raw.strip():
        return None
    parts = [p for p in raw.split(",") if p.strip()]
    if len(parts) != 4:
        raise AppError("bbox 需为 minx,miny,maxx,maxy 四个数值")
    try:
        minx, miny, maxx, maxy = (float(p) for p in parts)
    except ValueError as exc:
        raise AppError("bbox 需为 minx,miny,maxx,maxy 四个数值") from exc
    if max(abs(minx), abs(maxx)) > 180 or max(abs(miny), abs(maxy)) > 90:
        raise AppError("bbox 数值超出经纬度范围，请确认地图坐标系")
    if minx > maxx:
        minx, maxx = maxx, minx
    if miny > maxy:
        miny, maxy = maxy, miny
    return minx, miny, maxx, maxy


def _auto_per_module(env: tuple[float, float, float, float] | None) -> int:
    """未指定单模块上限时，按视野跨度（度）粗略换算缩放级别给出取值。"""
    if env is None:
        return 300
    span = max(env[2] - env[0], env[3] - env[1])
    if span >= 1.0:
        return 100
    if span >= 0.3:
        return 200
    if span >= 0.08:
        return 400
    if span >= 0.02:
        return 800
    return 1500


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


@router.get("/map", summary="地图渲染数据（按模块聚合，支持按视野取数）")
def map_features(
    module_ids: str | None = Query(None, description="逗号分隔的模块 id；不传则取全部启用的信息模块"),
    bbox: str | None = Query(
        None,
        description="地图视野范围 minx,miny,maxx,maxy（与业务库同为单位度）；传入后只取视野内要素",
    ),
    per_module: int | None = Query(
        None,
        ge=1,
        le=20000,
        description="单个模块的取数上限；不传则按视野范围自动取值，且会按 max_total / 模块数 摊薄",
    ),
    max_total: int = Query(6000, ge=100, le=60000, description="单次响应的要素总量上限（在各模块间均分）"),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    """按视野取数 + 逐模块限额。

    历史实现是「全表 order by id 取前 limit 条」：真实数据入库后 col_feature 有
    47 万余条（点 39.6 万 / 面 7.9 万），住宅小区、公司企业这类大模块按 id 排在最前，
    独自吃满整个 limit 额度，其余模块（尤其点位）一条都取不到，界面上就是看不到点位。
    现在改为：
      1. 逐模块 CROSS JOIN LATERAL ... LIMIT，模块之间互不挤占；
      2. 传 bbox 时用 f.geometry && ST_MakeEnvelope(...) 过滤，走 idx_col_feature_geometry
         的 GiST 索引，只搬运视野内的要素；
      3. 单模块上限还会按 max_total / 模块数 再摊薄一次，保证响应体不会随图层数线性膨胀。
    每个模块多取 1 条用于判断「视野内还有更多」，返回 truncated 供前端提示。
    """
    env = _parse_bbox(bbox)
    ids = _parse_module_ids(module_ids)
    if ids is not None and not ids:
        return ok([])

    # 两处查询都以 meta_info_module 单表为 FROM，条件用不带限定的列名，内层子查询才能引用
    module_where = "id = ANY(:ids)" if ids is not None else "is_active = TRUE"
    count_row = db.execute(
        text(f"SELECT count(*) FROM meta_info_module m WHERE {module_where}"),  # noqa: S608
        {"ids": ids} if ids is not None else {},
    ).scalar()
    module_count = int(count_row or 0)
    if not module_count:
        return ok([])

    # 视野越大、模块越多，单模块取值越收敛；再叠加一个总量摊薄，避免整屏图层各拿满额度
    per_module_limit = per_module if per_module is not None else _auto_per_module(env)
    per_module_limit = max(
        1, min(per_module_limit, max(10, max_total // module_count), max_total)
    )

    bbox_sql = ""
    if env:
        bbox_sql = f"AND f.geometry && ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, {_SRID})"
    sql = text(f"""
        SELECT m.id AS module_id, m.name AS module_name, m.geom_type AS geom_type, m.color AS color,
               g.id AS feature_id, g.code AS feature_code, g.name AS feature_name,
               g.status AS feature_status, g.feature_props AS feature_props,
               g.feature_geom AS feature_geom
          FROM (
                SELECT id, name, geom_type, color, layer_order
                  FROM meta_info_module
                 WHERE {module_where}
               ) m
          CROSS JOIN LATERAL (
                SELECT f.id,
                       f.code,
                       f.name,
                       f.status,
                       f.properties::text AS feature_props,
                       ST_AsGeoJSON(f.geometry, {_GEOJSON_PRECISION}) AS feature_geom
                  FROM col_feature f
                 WHERE f.module_id = m.id
                   {bbox_sql}
                 LIMIT :lim
               ) g
         ORDER BY m.layer_order, m.id, g.id
    """)
    params: dict[str, Any] = {"lim": per_module_limit + 1}
    if ids is not None:
        params["ids"] = ids
    if env:
        params.update(minx=env[0], miny=env[1], maxx=env[2], maxy=env[3])

    grouped: dict[int, dict] = {}
    for row in db.execute(sql, params):
        bucket = grouped.setdefault(
            row.module_id,
            {
                "module_id": row.module_id,
                "module_name": row.module_name,
                "geom_type": row.geom_type,
                "color": row.color or "#2d8cf0",
                "features": [],
                "returned": 0,
                "truncated": False,
            },
        )
        if len(bucket["features"]) >= per_module_limit:
            # 多取的那一条说明视野内/该模块还有更多数据
            bucket["truncated"] = True
            continue
        props: dict = {}
        if row.feature_props:
            try:
                props = json.loads(row.feature_props) or {}
            except ValueError:
                props = {}
        bucket["features"].append(
            FeatureMapOut(
                id=row.feature_id,
                module_id=row.module_id,
                code=row.feature_code,
                name=row.feature_name,
                geometry=geom_svc.loads_geojson(row.feature_geom),
                properties={
                    "id": row.feature_id,
                    "name": row.feature_name,
                    "code": row.feature_code,
                    "status": row.feature_status,
                    **props,
                },
            ).model_dump()
        )
    for bucket in grouped.values():
        bucket["returned"] = len(bucket["features"])
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
