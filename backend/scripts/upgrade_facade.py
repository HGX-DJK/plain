"""增量升级：补齐建筑物外景影像表与权限点（幂等，不影响已有数据）。

用法：python scripts/upgrade_facade.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.permissions import ALL_PERMISSIONS, BUILTIN_ROLES
from app.db.session import Base, SessionLocal, engine
from app.models import FacadeMedia  # noqa: F401  # 注册新表
from app.models.system import Permission, Role, role_permission


def create_tables() -> None:
    Base.metadata.create_all(engine)
    print(f">>> 表已就绪（共 {len(Base.metadata.tables)} 张）")


def sync_permissions() -> None:
    db = SessionLocal()
    try:
        existing = {p.code for p in db.query(Permission).all()}
        added = 0
        max_sort = db.query(Permission).count()
        for spec in ALL_PERMISSIONS:
            if spec["code"] in existing:
                continue
            max_sort += 1
            db.add(
                Permission(
                    code=spec["code"],
                    name=spec["name"],
                    module=spec["module"],
                    action=spec["action"],
                    perm_type=spec["perm_type"],
                    sort_order=max_sort,
                )
            )
            existing.add(spec["code"])
            added += 1
        db.flush()

        perm_map = {p.code: p.id for p in db.query(Permission).all()}
        linked = 0
        for role_code, spec in BUILTIN_ROLES.items():
            role = db.query(Role).filter(Role.code == role_code).first()
            if role is None:
                continue
            codes = spec["permissions"] or list(perm_map.keys())
            current = {
                row[0]
                for row in db.query(role_permission.c.permission_id)
                .filter(role_permission.c.role_id == role.id)
                .all()
            }
            for code in codes:
                perm_id = perm_map.get(code)
                if perm_id is None or perm_id in current:
                    continue
                db.execute(
                    role_permission.insert().values(role_id=role.id, permission_id=perm_id)
                )
                linked += 1

        db.commit()
        print(f">>> 新增权限点 {added} 个，补充角色授权 {linked} 条")
    finally:
        db.close()


if __name__ == "__main__":
    create_tables()
    sync_permissions()
    print("完成。")
