"""经纬度比对：申报坐标 vs 实测坐标。

实测坐标取采集几何的中心点（点要素即其本身，线/面要素取质心）。
偏差距离用球面大圆公式（haversine，平均半径 6371008.8m），
方位角用起点指向实测点的真北方位角。
"""
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.building import Building
from app.models.compare import ComparisonItem, ComparisonTask
from app.models.info import Feature
from app.models.system import Config
from app.services import geom as geom_svc

EARTH_RADIUS_M = 6371008.8

ISSUE_LABELS = {
    "ok": "合格",
    "over_threshold": "超差",
    "missing_declared": "缺申报坐标",
    "missing_measured": "缺实测坐标（无空间信息）",
    "invalid_coord": "坐标超出合法范围",
}


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """从申报点指向实测点的真北方位角（0–360°）。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def valid_lnglat(lng: Any, lat: Any) -> bool:
    try:
        lngf, latf = float(lng), float(lat)
    except (TypeError, ValueError):
        return False
    return -180 <= lngf <= 180 and -90 <= latf <= 90


def bearing_text(deg: float | None) -> str:
    """方位角转八方位描述，便于人工判读。"""
    if deg is None:
        return ""
    names = ["正北", "东北", "正东", "东南", "正南", "西南", "正西", "西北"]
    return names[int(((deg + 22.5) % 360) // 45) % 8]


def _collect_sources(db: Session, task: ComparisonTask) -> list[dict]:
    """把待比对的记录读成统一结构。"""
    rows: list[dict] = []
    if task.source_type == "building":
        q = (
            db.query(
                Building.id,
                Building.code,
                Building.name,
                Building.declared_lng,
                Building.declared_lat,
                func.ST_AsGeoJSON(func.ST_Centroid(Building.geometry)),
            )
            .filter(Building.geometry.isnot(None))
        )
        if task.source_ids:
            q = q.filter(Building.id.in_(task.source_ids))
        for rid, code, name, dlng, dlat, center in q.all():
            center_gj = geom_svc.loads_geojson(center)
            mlng, mlat = (center_gj["coordinates"] if center_gj else (None, None))
            rows.append(
                {
                    "source_type": "building",
                    "source_id": rid,
                    "code": code,
                    "name": name,
                    "declared_lng": dlng,
                    "declared_lat": dlat,
                    "measured_lng": mlng,
                    "measured_lat": mlat,
                }
            )
    else:
        q = (
            db.query(
                Feature.id,
                Feature.code,
                Feature.name,
                Feature.declared_lng,
                Feature.declared_lat,
                func.ST_AsGeoJSON(func.ST_Centroid(Feature.geometry)),
            )
            .filter(Feature.geometry.isnot(None))
        )
        if task.module_id:
            q = q.filter(Feature.module_id == task.module_id)
        if task.source_ids:
            q = q.filter(Feature.id.in_(task.source_ids))
        for rid, code, name, dlng, dlat, center in q.all():
            center_gj = geom_svc.loads_geojson(center)
            mlng, mlat = (center_gj["coordinates"] if center_gj else (None, None))
            rows.append(
                {
                    "source_type": "feature",
                    "source_id": rid,
                    "code": code,
                    "name": name,
                    "declared_lng": dlng,
                    "declared_lat": dlat,
                    "measured_lng": mlng,
                    "measured_lat": mlat,
                }
            )
    return rows


def evaluate_row(row: dict, threshold_m: float) -> dict:
    """单条记录的比对结论。"""
    declared_ok = valid_lnglat(row.get("declared_lng"), row.get("declared_lat"))
    measured_ok = valid_lnglat(row.get("measured_lng"), row.get("measured_lat"))

    if not declared_ok and not measured_ok:
        return {**row, "deviation_m": None, "bearing_deg": None,
                "passed": None, "issue": "invalid_coord", "threshold_m": threshold_m}
    if not declared_ok:
        return {**row, "deviation_m": None, "bearing_deg": None,
                "passed": None, "issue": "missing_declared", "threshold_m": threshold_m}
    if not measured_ok:
        return {**row, "deviation_m": None, "bearing_deg": None,
                "passed": None, "issue": "missing_measured", "threshold_m": threshold_m}

    deviation = haversine_m(
        row["declared_lng"], row["declared_lat"], row["measured_lng"], row["measured_lat"]
    )
    bearing = bearing_deg(
        row["declared_lng"], row["declared_lat"], row["measured_lng"], row["measured_lat"]
    )
    issue = "ok" if deviation <= threshold_m else "over_threshold"
    return {
        **row,
        "deviation_m": round(deviation, 2),
        "bearing_deg": round(bearing, 1),
        "passed": issue == "ok",
        "issue": issue,
        "threshold_m": threshold_m,
    }


def run_comparison(db: Session, task: ComparisonTask) -> dict:
    """执行一次比对：清空旧明细，重新计算并写库。

    注意：不能用 bulk delete（query(...).delete()），因为 task.items 是
    lazy="selectin" 会随任务一起加载，批量删除会把已加载的明细标记为 deleted，
    后续 flush/commit 时会抛出 “Instance has been deleted”。这里通过关系清理，
    交给 delete-orphan 级联完成删除。
    """
    task.items.clear()
    db.flush()
    now = datetime.now(timezone.utc)

    results = [evaluate_row(r, task.threshold_m) for r in _collect_sources(db, task)]
    passed = failed = 0
    for r in results:
        item = ComparisonItem(
            task_id=task.id,
            source_type=r["source_type"],
            source_id=r["source_id"],
            code=r["code"],
            name=r["name"],
            declared_lng=r["declared_lng"],
            declared_lat=r["declared_lat"],
            measured_lng=r["measured_lng"],
            measured_lat=r["measured_lat"],
            deviation_m=r["deviation_m"],
            bearing_deg=r["bearing_deg"],
            threshold_m=r["threshold_m"],
            passed=r["passed"],
            issue=r["issue"],
            created_at=now,
        )
        if valid_lnglat(r["declared_lng"], r["declared_lat"]):
            item.declared_geom = geom_svc.to_wkb_hex(
                {"type": "Point", "coordinates": [r["declared_lng"], r["declared_lat"]]}, "point"
            )
        if valid_lnglat(r["measured_lng"], r["measured_lat"]):
            item.measured_geom = geom_svc.to_wkb_hex(
                {"type": "Point", "coordinates": [r["measured_lng"], r["measured_lat"]]}, "point"
            )
        db.add(item)
        if r["passed"] is True:
            passed += 1
        elif r["passed"] is False:
            failed += 1

    task.total_count = len(results)
    task.passed_count = passed
    task.failed_count = failed
    task.status = "done"
    task.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "unknown": len(results) - passed - failed,
    }


def default_threshold(db: Session) -> float:
    value = db.query(Config.value).filter(Config.key == "compare.default_threshold_m").scalar()
    try:
        return float(value) if value else 10.0
    except (TypeError, ValueError):
        return 10.0
