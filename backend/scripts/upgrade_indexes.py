"""增量升级：补齐空间/模块索引（幂等，不影响已有数据）。

用途：现场库建表时若缺少下列索引，「数据采集」地图按视野取数会退化成全表扫描：
  - col_feature(module_id)：按模块取数、按模块过滤列表的主路径；
  - col_feature / bld_building / org_unit 的 GiST 空间索引：geometry && ST_MakeEnvelope(...) 视野查询。

用法：python scripts/upgrade_indexes.py
说明：CREATE INDEX IF NOT EXISTS 会阻塞写入，数据量大时建议在低峰执行；
      需要在线建索引用 ALTER/CREATE INDEX CONCURRENTLY（不能放在事务里，本脚本以 AUTOCOMMIT 执行）。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

# (索引名, DDL)：全部使用 IF NOT EXISTS，可重复执行
INDEX_DDL = [
    (
        "idx_col_feature_module",
        "CREATE INDEX IF NOT EXISTS idx_col_feature_module ON col_feature (module_id)",
    ),
    (
        "idx_col_feature_geometry",
        "CREATE INDEX IF NOT EXISTS idx_col_feature_geometry ON col_feature USING gist (geometry)",
    ),
    (
        "idx_bld_building_geometry",
        "CREATE INDEX IF NOT EXISTS idx_bld_building_geometry ON bld_building USING gist (geometry)",
    ),
    (
        "idx_org_unit_geometry",
        "CREATE INDEX IF NOT EXISTS idx_org_unit_geometry ON org_unit USING gist (geometry)",
    ),
    (
        "idx_cmp_item_declared_geom",
        "CREATE INDEX IF NOT EXISTS idx_cmp_item_declared_geom ON cmp_item USING gist (declared_geom)",
    ),
    (
        "idx_cmp_item_measured_geom",
        "CREATE INDEX IF NOT EXISTS idx_cmp_item_measured_geom ON cmp_item USING gist (measured_geom)",
    ),
]


def ensure_indexes() -> None:
    # 独立连接 + AUTOCOMMIT：每条 DDL 立即生效，不共用一个事务
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        existing = {
            row[0]
            for row in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
            )
        }
        for name, ddl in INDEX_DDL:
            if name in existing:
                print(f">>> 已存在：{name}")
                continue
            started = time.time()
            conn.execute(text(ddl))
            print(f">>> 已创建：{name}（{time.time() - started:.1f}s）")
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"目标库：{settings.pg_host}:{settings.pg_port}/{settings.pg_db}")
    ensure_indexes()
    print("完成。")
