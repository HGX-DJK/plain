"""建筑物基础数据采集（面状空间信息）+ 建筑-单位关联。"""
from fastapi import APIRouter, Depends, Query, Request
from geoalchemy2 import Geography
from sqlalchemy import cast, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import AppError, NotFound, ok, page_ok
from app.db.session import get_db
from app.models.building import Building, BuildingUnit, Unit
from app.models.system import User
from app.schemas.building import (
    BuildingOut,
    BuildingUnitOut,
    BuildingUnitUpsert,
    BuildingUpsert,
    UnitBriefInBuilding,
)
from app.schemas.common import PageParams
from app.services import geom as geom_svc
from app.services.audit import log_action

router = APIRouter(prefix="/buildings", tags=["建筑物采集"])

guard_view = require_permissions("building:view", "unit:view")
guard_write = require_permissions("building:create", "building:update", "building:delete")
guard_link = require_permissions("unit:link", "building:update")


def _geo_cast(col):
    """geometry -> geography 并保持与业务一致的 SRID（用于面积计算）。"""
    return cast(col, Geography(geometry_type="GEOMETRY", srid=settings.spatial_srid))


def _geom_exprs():
    return (
        func.ST_AsGeoJSON(Building.geometry).label("geometry_json"),
        func.ST_AsGeoJSON(func.ST_Centroid(Building.geometry)).label("center_json"),
        func.ST_Area(_geo_cast(Building.geometry)).label("area_m2"),
    )


def _relations(db: Session, building_id: int) -> list[dict]:
    rows = (
        db.query(BuildingUnit, Unit)
        .join(Unit, Unit.id == BuildingUnit.unit_id)
        .filter(BuildingUnit.building_id == building_id)
        .order_by(BuildingUnit.is_primary.desc(), BuildingUnit.id)
        .all()
    )
    return [
        UnitBriefInBuilding(
            relation_id=rel.id,
            unit_id=unit.id,
            name=unit.name,
            credit_code=unit.credit_code,
            relation_type=rel.relation_type,
            share_ratio=rel.share_ratio,
            is_primary=rel.is_primary,
        ).model_dump()
        for rel, unit in rows
    ]


def _build_out(building: Building, geometry_json, center_json, area_m2, units=None) -> dict:
    center = geom_svc.loads_geojson(center_json)
    lng = lat = None
    if center and center.get("type") == "Point":
        lng, lat = center["coordinates"]
    return BuildingOut(
        id=building.id,
        code=building.code,
        name=building.name,
        address=building.address,
        parcel_code=building.parcel_code,
        region_code=building.region_code,
        geometry=geom_svc.loads_geojson(geometry_json),
        declared_lng=building.declared_lng,
        declared_lat=building.declared_lat,
        center_lng=lng,
        center_lat=lat,
        area_m2=round(area_m2, 2) if area_m2 else None,
        floor_count=building.floor_count,
        building_height=building.building_height,
        usage=building.usage,
        structure_type=building.structure_type,
        build_year=building.build_year,
        ownership=building.ownership,
        status=building.status,
        attachments=building.attachments,
        extra=building.extra,
        remark=building.remark,
        created_at=building.created_at,
        updated_at=building.updated_at,
        units=units or [],
    ).model_dump()


@router.get("", summary="建筑物列表")
def list_buildings(
    pg: PageParams = Depends(),
    status: str | None = None,
    usage: str | None = None,
    region_code: str | None = None,
    unit_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(Building, *_geom_exprs())
    conds = []
    if pg.keyword:
        like = f"%{pg.keyword}%"
        conds.append(
            Building.name.ilike(like)
            | Building.code.ilike(like)
            | Building.address.ilike(like)
        )
    if status:
        conds.append(Building.status == status)
    if usage:
        conds.append(Building.usage == usage)
    if region_code:
        conds.append(Building.region_code == region_code)
    if unit_id:
        sub = (
            db.query(BuildingUnit.building_id)
            .filter(BuildingUnit.unit_id == unit_id)
            .subquery()
        )
        conds.append(Building.id.in_(sub))
    if conds:
        q = q.filter(*conds)

    count_q = db.query(func.count(Building.id))
    if conds:
        count_q = count_q.filter(*conds)
    total = count_q.scalar() or 0

    rows = q.order_by(Building.id.desc()).offset(pg.offset).limit(pg.page_size).all()
    return page_ok(
        [_build_out(b, gj, cj, area) for b, gj, cj, area in rows],
        total,
        pg.page,
        pg.page_size,
    )


@router.get("/summary", summary="建筑物统计")
def summary(db: Session = Depends(get_db), _: User = Depends(guard_view)):
    total = db.query(func.count(Building.id)).scalar() or 0
    by_status = (
        db.query(Building.status, func.count(Building.id))
        .group_by(Building.status)
        .all()
    )
    total_area = (
        db.query(func.sum(func.ST_Area(_geo_cast(Building.geometry)))).scalar() or 0
    )
    linked = db.query(func.count(func.distinct(BuildingUnit.building_id))).scalar() or 0
    return ok(
        {
            "total": total,
            "total_area_m2": round(float(total_area), 2),
            "linked_to_unit": linked,
            "unlinked": total - linked,
            "by_status": [{"status": s or "未填", "count": c} for s, c in by_status],
        }
    )


@router.get("/map", summary="建筑物地图数据")
def map_buildings(
    limit: int = Query(2000, ge=1, le=20000),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    rows = db.query(Building, *_geom_exprs()).order_by(Building.id).limit(limit).all()
    return ok(
        [
            {
                "id": b.id,
                "code": b.code,
                "name": b.name,
                "status": b.status,
                "usage": b.usage,
                "geometry": geom_svc.loads_geojson(gj),
            }
            for b, gj, cj, area in rows
        ]
    )


@router.get("/{building_id}", summary="建筑物详情（含关联单位）")
def get_building(
    building_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    row = db.query(Building, *_geom_exprs()).filter(Building.id == building_id).one_or_none()
    if row is None:
        raise NotFound("建筑物不存在")
    b, gj, cj, area = row
    return ok(_build_out(b, gj, cj, area, _relations(db, building_id)))


@router.post("", summary="新增建筑物")
def create_building(
    payload: BuildingUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    if db.query(Building).filter(Building.code == payload.code).first():
        raise AppError(f"建筑物编码 {payload.code} 已存在")
    # 建筑物必须是面状空间信息
    ewkb = geom_svc.to_wkb_hex(payload.geometry, "polygon")

    building = Building(
        **payload.model_dump(exclude={"geometry"}),
        geometry=ewkb,
        created_by=operator.id,
        updated_by=operator.id,
    )
    db.add(building)
    db.flush()
    log_action(db, operator, "building:create", target=building.code, ip=client_ip(request))
    db.commit()
    db.refresh(building)
    row = db.query(Building, *_geom_exprs()).filter(Building.id == building.id).one()
    return ok(_build_out(*row), "建筑物已保存")


@router.put("/{building_id}", summary="编辑建筑物")
def update_building(
    building_id: int,
    payload: BuildingUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    building = db.get(Building, building_id)
    if building is None:
        raise NotFound("建筑物不存在")
    dup = (
        db.query(Building)
        .filter(Building.code == payload.code, Building.id != building_id)
        .first()
    )
    if dup:
        raise AppError(f"建筑物编码 {payload.code} 已存在")

    for key, value in payload.model_dump(exclude={"geometry"}).items():
        setattr(building, key, value)
    if payload.geometry is not None:
        building.geometry = geom_svc.to_wkb_hex(payload.geometry, "polygon")
    building.updated_by = operator.id

    db.add(building)
    log_action(db, operator, "building:update", target=building.code, ip=client_ip(request))
    db.commit()
    db.refresh(building)
    row = db.query(Building, *_geom_exprs()).filter(Building.id == building_id).one()
    return ok(_build_out(*row, _relations(db, building_id)), "建筑物已更新")


@router.delete("/{building_id}", summary="删除建筑物")
def delete_building(
    building_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    building = db.get(Building, building_id)
    if building is None:
        raise NotFound("建筑物不存在")
    log_action(db, operator, "building:delete", target=building.code, ip=client_ip(request))
    db.delete(building)
    db.commit()
    return ok(None, "建筑物已删除")


# ---------------- 建筑-单位关联 ----------------
@router.post(
    "/{building_id}/units",
    summary="为建筑物关联单位",
)
def attach_unit(
    building_id: int,
    payload: BuildingUnitUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_link),
):
    building = db.get(Building, building_id)
    if building is None:
        raise NotFound("建筑物不存在")
    unit = db.get(Unit, payload.unit_id)
    if unit is None:
        raise NotFound("单位不存在")
    if payload.building_id not in (0, building_id):
        raise AppError("路径中的建筑物与请求体不一致")

    exist = (
        db.query(BuildingUnit)
        .filter(
            BuildingUnit.building_id == building_id,
            BuildingUnit.unit_id == payload.unit_id,
            BuildingUnit.relation_type == payload.relation_type,
        )
        .first()
    )
    if exist:
        raise AppError(f"该建筑物已以「{payload.relation_type}」关系关联此单位")

    if payload.is_primary:
        db.query(BuildingUnit).filter(BuildingUnit.building_id == building_id).update(
            {"is_primary": False}
        )

    rel = BuildingUnit(building_id=building_id, **payload.model_dump(exclude={"building_id"}))
    db.add(rel)
    db.flush()
    log_action(
        db, operator, "building:attach_unit",
        target=f"{building.code} <- {unit.name}", ip=client_ip(request),
    )
    db.commit()
    db.refresh(rel)
    return ok(
        BuildingUnitOut(
            id=rel.id, building_id=rel.building_id, unit_id=rel.unit_id,
            relation_type=rel.relation_type, share_ratio=rel.share_ratio,
            start_date=rel.start_date, end_date=rel.end_date,
            is_primary=rel.is_primary, remark=rel.remark,
            building_name=building.name, building_code=building.code,
            unit_name=unit.name, unit_credit_code=unit.credit_code,
        ).model_dump(),
        "已关联单位",
    )


@router.put("/{building_id}/units/{relation_id}", summary="修改建筑-单位关联")
def update_relation(
    building_id: int,
    relation_id: int,
    payload: BuildingUnitUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_link),
):
    rel = db.get(BuildingUnit, relation_id)
    if rel is None or rel.building_id != building_id:
        raise NotFound("关联关系不存在")
    for key in ("relation_type", "share_ratio", "start_date", "end_date", "is_primary", "remark", "unit_id"):
        value = getattr(payload, key)
        if value is not None:
            setattr(rel, key, value)
    if payload.is_primary:
        db.query(BuildingUnit).filter(
            BuildingUnit.building_id == building_id, BuildingUnit.id != rel.id
        ).update({"is_primary": False})
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return ok({"id": rel.id}, "关联已更新")


@router.delete("/{building_id}/units/{relation_id}", summary="解除建筑-单位关联")
def detach_unit(
    building_id: int,
    relation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_link),
):
    rel = db.get(BuildingUnit, relation_id)
    if rel is None or rel.building_id != building_id:
        raise NotFound("关联关系不存在")
    log_action(db, operator, "building:detach_unit", target=str(relation_id), ip=client_ip(request))
    db.delete(rel)
    db.commit()
    return ok(None, "已解除关联")
