"""初始化/重置数据库：建 PostGIS 扩展、建表、写入种子数据。

用法：python scripts/init_db.py
警告：会删除 public schema 下所有现有表（已授权操作）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.config import settings
from app.core.permissions import ALL_PERMISSIONS, BUILTIN_ROLES
from app.core.security import hash_password
from app.db.session import Base, engine
from app.models import (  # noqa: F401  # 保证模型全部注册
    Building,
    BuildingUnit,
    ComparisonItem,
    ComparisonTask,
    Config,
    FacadeMedia,
    Feature,
    InfoField,
    InfoModule,
    OperationLog,
    Permission,
    Role,
    Unit,
    User,
)
from app.api.v1.configs import CONFIG_META
from app.models.system import role_permission

DEFAULT_ADMIN = {"username": "admin", "password": "Admin@123", "real_name": "系统管理员"}


def reset(keep_extension: bool = True) -> None:
    with engine.begin() as conn:
        print(">>> 删除 public schema 下全部对象")
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        if not keep_extension:
            conn.execute(text("DROP EXTENSION IF EXISTS postgis CASCADE"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    print(">>> 已启用 PostGIS 扩展")


def create_tables() -> None:
    Base.metadata.create_all(engine)
    print(f">>> 已创建 {len(Base.metadata.tables)} 张表")


def seed() -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        # 1. 权限点
        perm_map: dict[str, Permission] = {}
        for idx, spec in enumerate(ALL_PERMISSIONS, start=1):
            perm = Permission(
                code=spec["code"],
                name=spec["name"],
                module=spec["module"],
                action=spec["action"],
                perm_type=spec["perm_type"],
                sort_order=idx,
            )
            db.add(perm)
            perm_map[spec["code"]] = perm
        db.flush()

        # 2. 内置角色
        for code, spec in BUILTIN_ROLES.items():
            role = Role(
                code=code,
                name=spec["name"],
                description=spec["description"],
                is_builtin=True,
            )
            db.add(role)
            db.flush()  # 先拿到 role.id 再挂权限
            if spec["permissions"] is not None:
                for perm_code in spec["permissions"]:
                    db.execute(
                        role_permission.insert().values(
                            role_id=role.id, permission_id=perm_map[perm_code].id
                        )
                    )
            else:
                # super_admin：代码内直接放行，这里也挂全部权限便于展示
                for perm in perm_map.values():
                    db.execute(
                        role_permission.insert().values(
                            role_id=role.id, permission_id=perm.id
                        )
                    )
        db.flush()

        # 3. 超级管理员账号
        super_role = db.query(Role).filter(Role.code == "super_admin").one()
        admin = User(
            username=DEFAULT_ADMIN["username"],
            real_name=DEFAULT_ADMIN["real_name"],
            password_hash=hash_password(DEFAULT_ADMIN["password"]),
            is_active=True,
            roles=[super_role],
        )
        db.add(admin)

        # 4. 系统参数
        for key, (value, label, group, value_type, description) in CONFIG_META.items():
            db.add(
                Config(
                    key=key,
                    value=value,
                    label=label,
                    group=group,
                    value_type=value_type,
                    description=description,
                )
            )

        db.commit()
        print(f">>> 种子数据完成：权限 {len(perm_map)} 项、角色 {len(BUILTIN_ROLES)} 个、参数 {len(CONFIG_META)} 项")
        print(f">>> 初始账号：{DEFAULT_ADMIN['username']} / {DEFAULT_ADMIN['password']}（请登录后修改）")
    finally:
        db.close()


if __name__ == "__main__":
    if input("确认清空并重建数据库？输入 yes 继续：").strip().lower() != "yes":
        print("已取消")
        sys.exit(0)
    print(f"目标库：{settings.pg_host}:{settings.pg_port}/{settings.pg_db}")
    reset()
    create_tables()
    seed()
    print("完成。")
