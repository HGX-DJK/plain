"""GeoJSON 校验与 PostGIS 几何写入/读取辅助。

写入：GeoJSON -> shapely -> EWKT 文本（geoalchemy2 经 ST_GeomFromEWKT 入库）
读取：SELECT ST_AsGeoJSON(geometry) AS ...  -> dict
"""
import json
from typing import Any

from sqlalchemy.orm import Session
from shapely import set_srid
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.core.config import settings
from app.core.errors import AppError
from app.models.info import GEOJSON_TYPE_BY_GEOM, GEOM_TYPES


def loads_geojson(value: Any) -> dict | None:
    """把 ST_AsGeoJSON 返回的字符串转成 dict。"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def generate_code(module, db: Session) -> str:
    """按「模块编码-日期-流水号」生成要素编号，如 DWROOF-261028-0001。"""
    from datetime import datetime

    from app.models.info import Feature

    prefix = f"{module.code.upper()}-{datetime.now().strftime('%y%m%d')}"
    same_day = (
        db.query(Feature)
        .filter(Feature.code.like(f"{prefix}-%"))
        .count()
    )
    return f"{prefix}-{same_day + 1:04d}"



def normalize_geojson(geo: Any) -> dict:
    """接受 GeoJSON dict，或 maptalks 的 {type:'Feature',...} / 裸几何对象。"""
    if geo is None:
        raise AppError("缺少空间信息（geometry）")
    if isinstance(geo, str):
        import json

        try:
            geo = json.loads(geo)
        except ValueError as exc:
            raise AppError("空间信息不是合法 JSON") from exc
    if not isinstance(geo, dict):
        raise AppError("空间信息格式错误，应为 GeoJSON 对象")
    if geo.get("type") == "Feature":
        geo = geo.get("geometry")
        if not isinstance(geo, dict):
            raise AppError("GeoJSON Feature 缺少 geometry")
    return geo


def _close_ring(ring: Any) -> list[list[float]]:
    """规范化单个环：去重、去尾点、自动闭合；顶点不足 3 个时报错。"""
    if not isinstance(ring, (list, tuple)) or not ring:
        raise AppError("面状几何的环缺少坐标")
    points: list[list[float]] = []
    for pt in ring:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            raise AppError("面状几何坐标格式错误，应为 [经度, 纬度]")
        try:
            x, y = float(pt[0]), float(pt[1])
        except (TypeError, ValueError) as exc:
            raise AppError("面状几何坐标必须是数字") from exc
        cur = [x, y]
        if not points or points[-1] != cur:
            points.append(cur)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        raise AppError("面的环至少需要 3 个互不相同的顶点")
    points.append(list(points[0]))
    return points


def _close_polygon(polygon: Any) -> list[list[list[float]]]:
    """规范化一个面片：外环 + 若干内环（洞）。"""
    if not isinstance(polygon, (list, tuple)) or not polygon:
        raise AppError("面状几何缺少坐标")
    return [_close_ring(ring) for ring in polygon]


def normalize_polygon_rings(gj: dict) -> dict:
    """闭合 Polygon / MultiPolygon 的所有环，兼容挖洞与飞地（MultiPolygon）。"""
    gtype = gj.get("type")
    coords = gj.get("coordinates")
    if gtype == "Polygon":
        return {**gj, "coordinates": _close_polygon(coords)}
    if gtype == "MultiPolygon":
        if not isinstance(coords, (list, tuple)) or not coords:
            raise AppError("面状几何缺少坐标")
        return {**gj, "coordinates": [_close_polygon(p) for p in coords]}
    return gj


# 常见拓扑错误的友好提示（shapely explain_validity 的英文原因 -> 中文说明）
_VALIDITY_HINTS = (
    ("Ring Self-intersection", "环自相交"),
    ("Hole lies outside shell", "挖洞超出外环"),
    ("Holes are nested", "洞相互嵌套"),
    ("Interior is disconnected", "洞把面切成了多块，请改用飞地"),
    ("Nested shells", "面片相互嵌套"),
    ("Self-intersection", "边界自相交"),
)


def _validity_hint(reason: str) -> str:
    for key, hint in _VALIDITY_HINTS:
        if key in reason:
            return hint
    return "拓扑不合法"


def to_wkb_hex(geo: Any, expected_geom_type: str | None = None) -> str:
    """校验并转换为带 SRID 的 EWKT 文本（geoalchemy2 写入用）。"""
    gj = normalize_geojson(geo)
    gtype = gj.get("type")
    if not gtype:
        raise AppError("空间信息缺少 type")

    if expected_geom_type:
        if expected_geom_type not in GEOM_TYPES:
            raise AppError(f"不支持的空间类型：{expected_geom_type}")
        allowed = GEOJSON_TYPE_BY_GEOM[expected_geom_type]
        if gtype not in allowed:
            raise AppError(
                f"该信息模块要求「{expected_geom_type}」类型，"
                f"实际传入「{gtype}」（允许：{', '.join(allowed)}）"
            )

    if gtype in ("Polygon", "MultiPolygon"):
        gj = normalize_polygon_rings(gj)

    try:
        geom: BaseGeometry = shape(gj)
    except (ValueError, TypeError) as exc:
        raise AppError(f"空间信息解析失败：{exc}") from exc
    if geom.is_empty:
        raise AppError("空间信息为空几何")
    if gtype in ("Polygon", "MultiPolygon"):
        if not geom.is_valid:
            from shapely.validation import explain_validity

            reason = explain_validity(geom)
            raise AppError(
                f"面状几何不合法（{_validity_hint(reason)}），"
                "请检查边界自相交、洞是否落在面内、飞地面片是否重叠"
            )

    geom = set_srid(geom, settings.spatial_srid)
    return f"SRID={settings.spatial_srid};{geom.wkt}"


def centroid_lnglat(gj: dict) -> tuple[float, float]:
    """GeoJSON 几何的质心经纬度（实测坐标取点用）。"""
    geom = shape(normalize_geojson(gj))
    point = geom.centroid
    return round(point.x, 8), round(point.y, 8)


def to_shape(gj: Any) -> BaseGeometry:
    return shape(normalize_geojson(gj))
