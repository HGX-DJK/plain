"""采集数据经纬度比对：任务发起、结果查询、地图可视化与导出。"""
import csv
import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import AppError, NotFound, ok, page_ok
from app.db.session import get_db
from app.models.compare import SOURCE_TYPES, ComparisonItem, ComparisonTask
from app.models.info import InfoModule
from app.models.system import User
from app.schemas.building import ComparisonItemUpdate, ComparisonTaskUpsert
from app.schemas.common import PageParams
from app.services import compare as cmp_svc
from app.services import geom as geom_svc
from app.services.audit import log_action

router = APIRouter(prefix="/compare", tags=["经纬度比对"])

guard_view = require_permissions("compare:view")
guard_run = require_permissions("compare:run")
guard_delete = require_permissions("compare:delete")
guard_export = require_permissions("compare:export")


def _task_out(task: ComparisonTask) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "source_type": task.source_type,
        "module_id": task.module_id,
        "module_name": getattr(task, "module_name", None),
        "threshold_m": task.threshold_m,
        "status": task.status,
        "total_count": task.total_count,
        "passed_count": task.passed_count,
        "failed_count": task.failed_count,
        "description": task.description,
        "created_at": task.created_at,
        "finished_at": task.finished_at,
    }


def _item_out(item: ComparisonItem) -> dict:
    return {
        "id": item.id,
        "task_id": item.task_id,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "code": item.code,
        "name": item.name,
        "declared_lng": item.declared_lng,
        "declared_lat": item.declared_lat,
        "measured_lng": item.measured_lng,
        "measured_lat": item.measured_lat,
        "deviation_m": item.deviation_m,
        "bearing_deg": item.bearing_deg,
        "bearing_text": cmp_svc.bearing_text(item.bearing_deg),
        "threshold_m": item.threshold_m,
        "passed": item.passed,
        "issue": item.issue,
        "issue_label": cmp_svc.ISSUE_LABELS.get(item.issue or "", item.issue),
        "remark": item.remark,
    }


@router.get("/tasks", summary="比对任务列表")
def list_tasks(
    pg: PageParams = Depends(),
    source_type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(ComparisonTask, InfoModule.name)
    q = q.outerjoin(InfoModule, InfoModule.id == ComparisonTask.module_id)
    if pg.keyword:
        q = q.filter(ComparisonTask.name.ilike(f"%{pg.keyword}%"))
    if source_type:
        if source_type not in SOURCE_TYPES:
            raise AppError(f"source_type 需为 {'/'.join(SOURCE_TYPES)}")
        q = q.filter(ComparisonTask.source_type == source_type)

    count_q = db.query(func.count(ComparisonTask.id))
    if pg.keyword:
        count_q = count_q.filter(ComparisonTask.name.ilike(f"%{pg.keyword}%"))
    if source_type:
        count_q = count_q.filter(ComparisonTask.source_type == source_type)
    total = count_q.scalar() or 0

    rows = q.order_by(ComparisonTask.id.desc()).offset(pg.offset).limit(pg.page_size).all()
    items = []
    for task, module_name in rows:
        data = _task_out(task)
        data["module_name"] = module_name
        items.append(data)
    return page_ok(items, total, pg.page, pg.page_size)


@router.get("/tasks/{task_id}", summary="比对任务详情")
def get_task(
    task_id: int,
    issue: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    row = (
        db.query(ComparisonTask, InfoModule.name)
        .outerjoin(InfoModule, InfoModule.id == ComparisonTask.module_id)
        .filter(ComparisonTask.id == task_id)
        .one_or_none()
    )
    if row is None:
        raise NotFound("比对任务不存在")
    task, module_name = row
    data = _task_out(task)
    data["module_name"] = module_name

    item_q = db.query(ComparisonItem).filter(ComparisonItem.task_id == task_id)
    if issue:
        item_q = item_q.filter(ComparisonItem.issue == issue)
    data["items"] = [_item_out(i) for i in item_q.order_by(ComparisonItem.id).all()]
    return ok(data)


@router.post("/tasks", summary="发起比对任务（立即执行）")
def create_task(
    payload: ComparisonTaskUpsert,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_run),
):
    if payload.source_type not in SOURCE_TYPES:
        raise AppError(f"source_type 需为 {'/'.join(SOURCE_TYPES)}")
    if payload.source_type == "feature" and payload.module_id:
        module = db.get(InfoModule, payload.module_id)
        if module is None:
            raise NotFound("信息模块不存在")
    if payload.threshold_m <= 0:
        raise AppError("阈值必须大于 0 米")

    task = ComparisonTask(
        name=payload.name,
        source_type=payload.source_type,
        module_id=payload.module_id if payload.source_type == "feature" else None,
        threshold_m=payload.threshold_m,
        description=payload.description,
        source_ids=payload.source_ids or None,
        created_by=operator.id,
        status="running",
    )
    db.add(task)
    db.flush()

    result = cmp_svc.run_comparison(db, task)
    log_action(
        db, operator, "compare:run", target=task.name,
        detail=result, ip=client_ip(request),
    )
    db.commit()
    return ok({**_task_out(task), "summary": result}, "比对完成")


@router.post("/tasks/{task_id}/rerun", summary="重新执行比对")
def rerun_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_run),
):
    task = db.get(ComparisonTask, task_id)
    if task is None:
        raise NotFound("比对任务不存在")
    task.status = "running"
    db.add(task)
    db.flush()
    result = cmp_svc.run_comparison(db, task)
    log_action(
        db, operator, "compare:rerun", target=task.name,
        detail=result, ip=client_ip(request),
    )
    db.commit()
    return ok({**_task_out(task), "summary": result}, "重新比对完成")


@router.delete("/tasks/{task_id}", summary="删除比对任务")
def delete_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_delete),
):
    task = db.get(ComparisonTask, task_id)
    if task is None:
        raise NotFound("比对任务不存在")
    log_action(db, operator, "compare:delete", target=task.name, ip=client_ip(request))
    db.delete(task)
    db.commit()
    return ok(None, "比对任务已删除")


@router.put("/items/{item_id}", summary="填写比对明细备注")
def update_item(
    item_id: int,
    payload: ComparisonItemUpdate,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_view),
):
    item = db.get(ComparisonItem, item_id)
    if item is None:
        raise NotFound("比对明细不存在")
    item.remark = payload.remark
    db.add(item)
    db.commit()
    return ok(_item_out(item), "备注已保存")


@router.get("/tasks/{task_id}/map", summary="比对结果地图数据（点对与连线）")
def task_map(
    task_id: int,
    limit: int = Query(5000, ge=1, le=20000),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    if db.get(ComparisonTask, task_id) is None:
        raise NotFound("比对任务不存在")
    rows = (
        db.query(
            ComparisonItem.id,
            ComparisonItem.code,
            ComparisonItem.name,
            ComparisonItem.passed,
            ComparisonItem.deviation_m,
            func.ST_AsGeoJSON(ComparisonItem.declared_geom).label("d_geo"),
            func.ST_AsGeoJSON(ComparisonItem.measured_geom).label("m_geo"),
        )
        .filter(ComparisonItem.task_id == task_id)
        .order_by(ComparisonItem.id)
        .limit(limit)
        .all()
    )
    points = []
    lines = []
    for iid, code, name, passed, dev, d_geo, m_geo in rows:
        pair_label = code or name or str(iid)
        color = "#18a058" if passed else ("#999" if passed is None else "#d03050")
        d = geom_svc.loads_geojson(d_geo)
        m = geom_svc.loads_geojson(m_geo)
        if d:
            points.append(
                {
                    "id": f"d{iid}", "pair_id": iid, "kind": "declared",
                    "label": pair_label, "color": color, "geometry": d,
                }
            )
        if m:
            points.append(
                {
                    "id": f"m{iid}", "pair_id": iid, "kind": "measured",
                    "label": pair_label, "color": color, "geometry": m,
                }
            )
        if d and m:
            lines.append(
                {
                    "id": f"l{iid}", "pair_id": iid,
                    "label": f"{pair_label} 偏差 {dev}m",
                    "color": color,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [d["coordinates"], m["coordinates"]],
                    },
                }
            )
    return ok({"points": points, "lines": lines})


@router.get("/tasks/{task_id}/export.csv", summary="导出比对明细 CSV")
def export_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(guard_export),
):
    task = db.get(ComparisonTask, task_id)
    if task is None:
        raise NotFound("比对任务不存在")
    rows = (
        db.query(ComparisonItem)
        .filter(ComparisonItem.task_id == task_id)
        .order_by(ComparisonItem.id)
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "序号", "编号", "名称", "申报经度", "申报纬度", "实测经度", "实测纬度",
            "偏差(米)", "方位角(度)", "方位", "阈值(米)", "结论", "备注",
        ]
    )
    for idx, item in enumerate(rows, start=1):
        writer.writerow(
            [
                idx, item.code, item.name, item.declared_lng, item.declared_lat,
                item.measured_lng, item.measured_lat, item.deviation_m,
                item.bearing_deg, cmp_svc.bearing_text(item.bearing_deg),
                item.threshold_m,
                cmp_svc.ISSUE_LABELS.get(item.issue or "", item.issue),
                item.remark,
            ]
        )
    buffer.seek(0)
    # HTTP 头部只能是 latin-1，中文文件名需按 RFC 5987 编码，同时给 ASCII 兜底名
    filename = f"compare_{task.name or task_id}.csv"
    disposition = (
        f'attachment; filename="compare_{task_id}.csv"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return StreamingResponse(
        iter(["\ufeff", buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )
