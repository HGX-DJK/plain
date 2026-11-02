"""清理已废弃的系统参数（底图相关与坐标系 SRID）。

底图改由前端运行时配置提供、坐标系固定按 WGS84/CGCS2000 处理后，
库里遗留的 map.basemap_type / map.tianditu_tk / map.custom_tile_url / map.srid
可以直接删除，避免在「系统设置-参数配置」里继续出现。

用法（在 backend 目录下）：
    ../.venv/Scripts/python.exe scripts/cleanup_legacy_configs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.configs import LEGACY_KEYS
from app.db.session import SessionLocal
from app.models.system import Config


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.query(Config).filter(Config.key.in_(LEGACY_KEYS)).all()
        for row in rows:
            print(f"删除参数 {row.key}（{row.label}）")
            db.delete(row)
        db.commit()
        print(f"完成：共删除 {len(rows)} 项废弃参数")
    finally:
        db.close()


if __name__ == "__main__":
    main()
