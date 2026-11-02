"""系统参数（含地图与比对配置）与操作日志。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_current_user, require_permissions
from app.core.errors import NotFound, ok, page_ok
from app.db.session import get_db
from app.models.system import Config, OperationLog, User
from app.schemas.common import PageParams
from app.schemas.system import ConfigOut, ConfigUpsert
from app.services.audit import log_action

router = APIRouter(tags=["系统设置-参数"])

guard_view = require_permissions("system:view")
guard_config = require_permissions("system:config")

# 参数键 -> (默认值, 显示名称, 分组, 值类型, 说明)，初始化与前端展示都以此为准
CONFIG_META = {
    "system.name": ("一标六实数据采集系统", "系统名称", "general", "string", "登录页与系统顶栏显示的标题"),
    "map.center_lng": ("116.397428", "中心经度", "map", "number", "按 WGS84/CGCS2000 填写"),
    "map.center_lat": ("39.90923", "中心纬度", "map", "number", "按 WGS84/CGCS2000 填写"),
    "map.zoom": (str(settings.map_default_zoom), "默认缩放级别", "map", "number", "打开地图时的初始层级"),
    "map.max_zoom": ("18", "最大缩放级别", "map", "number", "地图允许放大的最高层级"),
    "compare.default_threshold_m": (
        str(settings.compare_default_threshold_m),
        "超差阈值（米）",
        "compare",
        "number",
        "实测与采集坐标比对的默认允许偏差",
    ),
    "collect.auto_fill_center": (
        "true",
        "自动写入实测坐标",
        "collect",
        "boolean",
        "保存采集数据时，用几何中心作为该要素的实测坐标",
    ),
}


# 已废弃的参数键：底图改由前端 public/js/config.js 配置，历史库中的残留不再展示/下发
LEGACY_KEYS = {
    "map.basemap_type",
    "map.tianditu_tk",
    "map.custom_tile_url",
    "map.srid",
}


def config_map(db: Session) -> dict[str, str]:
    return {c.key: (c.value or "") for c in db.query(Config).all()}


def as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


@router.get("/public/bootstrap", summary="前端启动配置（免登录）")
def bootstrap(db: Session = Depends(get_db)):
    """登录页与地图初始化需要的最小配置。

    底图瓦片地址、子域与坐标系由前端 public/js/config.js 配置（内网/离线环境），
    后端不再下发天地图密钥等公网相关参数。
    """
    cfg = config_map(db)
    return ok(
        {
            "app_name": cfg.get("system.name", CONFIG_META["system.name"][0]),
            "center": [
                as_float(cfg.get("map.center_lng"), 116.397428),
                as_float(cfg.get("map.center_lat"), 39.90923),
            ],
            "zoom": int(as_float(cfg.get("map.zoom"), settings.map_default_zoom)),
            "max_zoom": int(as_float(cfg.get("map.max_zoom"), 18)),
            "default_threshold_m": as_float(
                cfg.get("compare.default_threshold_m"),
                settings.compare_default_threshold_m,
            ),
        }
    )


@router.get("/configs", summary="系统参数列表")
def list_configs(
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
    group: str | None = None,
):
    q = db.query(Config).filter(Config.key.notin_(LEGACY_KEYS))
    if group:
        q = q.filter(Config.group == group)
    rows = q.order_by(Config.group, Config.key).all()
    # 显示名称与说明统一以 CONFIG_META 为准，老库里留存的旧名称也能自动纠正
    result = []
    for c in rows:
        item = ConfigOut.model_validate(c).model_dump()
        meta = CONFIG_META.get(c.key)
        if meta:
            item["label"] = meta[1]
            item["description"] = item["description"] or meta[4]
        result.append(item)
    return ok(result)


@router.put("/configs", summary="批量保存系统参数")
def upsert_configs(
    items: list[ConfigUpsert],
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_config),
):
    changed = []
    for item in items:
        meta = CONFIG_META.get(item.key, (None, None, item.group, item.value_type, None))
        row = db.query(Config).filter(Config.key == item.key).one_or_none()
        if row is None:
            row = Config(
                key=item.key,
                value=item.value,
                label=item.label or meta[1],
                group=item.group or meta[2],
                value_type=item.value_type or meta[3],
                description=item.description or meta[4],
            )
            db.add(row)
        else:
            row.value = item.value
            if item.label:
                row.label = item.label
            if item.description:
                row.description = item.description
        changed.append(item.key)
    log_action(db, operator, "config:update", detail={"keys": changed}, ip=client_ip(request))
    db.commit()
    return ok(None, f"已保存 {len(changed)} 项参数")


@router.delete("/configs/{config_id}", summary="删除自定义参数")
def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(guard_config),
):
    row = db.get(Config, config_id)
    if row is None:
        raise NotFound("参数不存在")
    log_action(db, operator, "config:delete", target=row.key, ip=None)
    db.delete(row)
    db.commit()
    return ok(None, "参数已删除")


@router.get("/logs", summary="操作日志")
def list_logs(
    pg: PageParams = Depends(),
    action: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
):
    q = db.query(OperationLog)
    if pg.keyword:
        like = f"%{pg.keyword}%"
        q = q.filter(OperationLog.username.ilike(like) | OperationLog.target.ilike(like))
    if action:
        q = q.filter(OperationLog.action == action)
    total = q.count()
    rows = (
        q.order_by(OperationLog.id.desc()).offset(pg.offset).limit(pg.page_size).all()
    )
    return page_ok(
        [
            {
                "id": r.id,
                "username": r.username,
                "action": r.action,
                "target": r.target,
                "detail": r.detail,
                "ip": r.ip,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        total,
        pg.page,
        pg.page_size,
    )
