"""工作台汇总统计。"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permissions
from app.core.errors import ok
from app.db.session import get_db
from app.models.building import Building, BuildingUnit, Unit
from app.models.compare import ComparisonTask
from app.models.info import Feature, InfoModule
from app.models.system import User

router = APIRouter(prefix="/dashboard", tags=["工作台"])


@router.get("/summary", summary="工作台汇总")
def summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    feature_total = db.query(func.count(Feature.id)).scalar() or 0
    module_total = db.query(func.count(InfoModule.id)).scalar() or 0
    building_total = db.query(func.count(Building.id)).scalar() or 0
    unit_total = db.query(func.count(Unit.id)).scalar() or 0
    linked = db.query(func.count(func.distinct(BuildingUnit.building_id))).scalar() or 0

    recent_tasks = (
        db.query(ComparisonTask)
        .order_by(ComparisonTask.id.desc())
        .limit(5)
        .all()
    )
    tasks = [
        {
            "id": t.id,
            "name": t.name,
            "status": t.status,
            "total_count": t.total_count,
            "passed_count": t.passed_count,
            "failed_count": t.failed_count,
            "created_at": t.created_at,
        }
        for t in recent_tasks
    ]

    by_geom = (
        db.query(InfoModule.geom_type, func.count(Feature.id))
        .outerjoin(Feature, Feature.module_id == InfoModule.id)
        .group_by(InfoModule.geom_type)
        .all()
    )
    return ok(
        {
            "module_total": module_total,
            "feature_total": feature_total,
            "building_total": building_total,
            "unit_total": unit_total,
            "building_linked": linked,
            "building_unlinked": building_total - linked,
            "recent_tasks": tasks,
            "features_by_geom": [{"geom_type": g or "无", "count": c} for g, c in by_geom],
        }
    )
