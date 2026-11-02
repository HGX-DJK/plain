"""建筑物所在单位信息采集。"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import AppError, NotFound, ok, page_ok
from app.db.session import get_db
from app.models.building import Building, BuildingUnit, Unit
from app.models.system import User
from app.schemas.building import UnitOut, UnitUpsert
from app.schemas.common import PageParams
from app.services import geom as geom_svc
from app.services.audit import log_action

router = APIRouter(prefix="/units", tags=["单位信息采集"])

guard_view = require_permissions("unit:view")
guard_write = require_permissions("unit:create", "unit:update", "unit:delete")


def _building_counts(db: Session) -> dict[int, int]:
    rows = (
        db.query(BuildingUnit.unit_id, func.count(func.distinct(BuildingUnit.building_id)))
        .group_by(BuildingUnit.unit_id)
        .all()
    )
    return dict(rows)


def _to_out(unit: Unit, building_count: int | None = None, geometry=None) -> dict:
    return UnitOut(
        id=unit.id,
        name=unit.name,
        credit_code=unit.credit_code,
        unit_type=unit.unit_type,
        legal_person=unit.legal_person,
        contact_name=unit.contact_name,
        phone=unit.phone,
        email=unit.email,
        address=unit.address,
        geometry=geometry,
        remark=unit.remark,
        created_at=unit.created_at,
        building_count=building_count,
    ).model_dump()


def _unit_buildings(db: Session, unit_id: int) -> list[dict]:
    rows = (
        db.query(BuildingUnit, Building)
        .join(Building, Building.id == BuildingUnit.building_id)
        .filter(BuildingUnit.unit_id == unit_id)
        .order_by(BuildingUnit.is_primary.desc(), Building.id)
        .all()
    )
    return [
        {
            "relation_id": rel.id,
            "building_id": b.id,
            "building_code": b.code,
            "building_name": b.name,
            "address": b.address,
            "status": b.status,
            "relation_type": rel.relation_type,
            "share_ratio": rel.share_ratio,
            "start_date": rel.start_date,
            "end_date": rel.end_date,
            "is_primary": rel.is_primary,
            "remark": rel.remark,
        }
        for rel, b in rows
    ]


@router.get("", summary="单位列表")
def list_units(
    pg: PageParams = Depends(),
    unit_type: str | None = None,
    has_building: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(Unit)
    if pg.keyword:
        like = f"%{pg.keyword}%"
        q = q.filter(
            Unit.name.ilike(like)
            | Unit.credit_code.ilike(like)
            | Unit.legal_person.ilike(like)
            | Unit.address.ilike(like)
        )
    if unit_type:
        q = q.filter(Unit.unit_type == unit_type)
    if has_building is True:
        q = q.filter(Unit.id.in_(db.query(BuildingUnit.unit_id).subquery()))
    elif has_building is False:
        q = q.filter(~Unit.id.in_(db.query(BuildingUnit.unit_id).subquery()))

    total = q.count()
    rows = q.order_by(Unit.id.desc()).offset(pg.offset).limit(pg.page_size).all()
    counts = _building_counts(db)
    return page_ok(
        [_to_out(u, counts.get(u.id, 0)) for u in rows], total, pg.page, pg.page_size
    )


@router.get("/types", summary="已使用的单位类型")
def list_unit_types(db: Session = Depends(get_db), _: User = Depends(guard_view)):
    rows = (
        db.query(Unit.unit_type, func.count(Unit.id))
        .filter(Unit.unit_type.isnot(None))
        .group_by(Unit.unit_type)
        .all()
    )
    return ok([{"value": t, "count": c} for t, c in rows])


@router.get("/{unit_id}", summary="单位详情（含关联建筑物）")
def get_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise NotFound("单位不存在")
    geometry = (
        geom_svc.loads_geojson(
            db.query(func.ST_AsGeoJSON(Unit.geometry)).filter(Unit.id == unit_id).scalar()
        )
        if unit.geometry
        else None
    )
    data = _to_out(unit, len(_unit_buildings(db, unit_id)), geometry)
    data["buildings"] = _unit_buildings(db, unit_id)
    return ok(data)


@router.post("", summary="新增单位")
def create_unit(
    payload: UnitUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    if payload.credit_code:
        if db.query(Unit).filter(Unit.credit_code == payload.credit_code).first():
            raise AppError(f"统一社会信用代码 {payload.credit_code} 已存在")
    data = payload.model_dump(exclude={"geometry"})
    unit = Unit(**data, created_by=operator.id)
    if payload.geometry is not None:
        unit.geometry = geom_svc.to_wkb_hex(payload.geometry, "point")
    db.add(unit)
    db.flush()
    log_action(db, operator, "unit:create", target=unit.name, ip=client_ip(request))
    db.commit()
    db.refresh(unit)
    return ok(_to_out(unit, 0), "单位已创建")


@router.put("/{unit_id}", summary="编辑单位")
def update_unit(
    unit_id: int,
    payload: UnitUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise NotFound("单位不存在")
    if payload.credit_code:
        dup = (
            db.query(Unit)
            .filter(Unit.credit_code == payload.credit_code, Unit.id != unit_id)
            .first()
        )
        if dup:
            raise AppError(f"统一社会信用代码 {payload.credit_code} 已被其他单位使用")

    for key, value in payload.model_dump(exclude={"geometry"}).items():
        setattr(unit, key, value)
    if payload.geometry is not None:
        unit.geometry = geom_svc.to_wkb_hex(payload.geometry, "point")
    db.add(unit)
    log_action(db, operator, "unit:update", target=unit.name, ip=client_ip(request))
    db.commit()
    db.refresh(unit)
    return ok(_to_out(unit, len(_unit_buildings(db, unit_id))), "单位已更新")


@router.delete("/{unit_id}", summary="删除单位（同时解除关联）")
def delete_unit(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_write),
):
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise NotFound("单位不存在")
    linked = len(_unit_buildings(db, unit_id))
    log_action(
        db, operator, "unit:delete", target=unit.name,
        detail={"linked_buildings": linked}, ip=client_ip(request),
    )
    db.delete(unit)
    db.commit()
    return ok({"unlinked_buildings": linked}, "单位已删除")


@router.get("/{unit_id}/buildings", summary="单位关联的建筑物列表")
def unit_buildings(
    unit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    if db.get(Unit, unit_id) is None:
        raise NotFound("单位不存在")
    return ok(_unit_buildings(db, unit_id))


@router.get("/positions", summary="单位点位地图数据")
def unit_positions(
    limit: int = Query(2000, ge=1, le=20000),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    rows = (
        db.query(Unit.id, Unit.name, Unit.unit_type, func.ST_AsGeoJSON(Unit.geometry))
        .filter(Unit.geometry.isnot(None))
        .order_by(Unit.id)
        .limit(limit)
        .all()
    )
    return ok(
        [
            {
                "id": r[0],
                "name": r[1],
                "unit_type": r[2],
                "geometry": geom_svc.loads_geojson(r[3]),
            }
            for r in rows
        ]
    )
