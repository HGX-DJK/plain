"""系统设置：用户、角色、权限、系统参数、操作日志。"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.common import IdMixin, TimestampMixin

# ---- 关联表 ----
user_role = Table(
    "sys_user_role",
    Base.metadata,
    Column("user_id", ForeignKey("sys_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True),
)

role_permission = Table(
    "sys_role_permission",
    Base.metadata,
    Column("role_id", ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        ForeignKey("sys_permission.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(128))
    dept: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_role, back_populates="users", lazy="selectin"
    )


class Role(Base, IdMixin, TimestampMixin):
    __tablename__ = "sys_role"
    __table_args__ = (UniqueConstraint("code", name="uq_sys_role_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary=user_role, back_populates="roles", lazy="selectin"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permission, back_populates="roles", lazy="selectin"
    )


class Permission(Base, IdMixin):
    """权限点。type=menu 控制前端菜单可见性，type=action 控制接口/按钮。"""

    __tablename__ = "sys_permission"

    code: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str | None] = mapped_column(String(64))
    perm_type: Mapped[str] = mapped_column(String(16), default="action", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permission, back_populates="permissions", lazy="selectin"
    )


class Config(Base, IdMixin, TimestampMixin):
    """系统参数。前端启动时拉取，用于天地图 tk、默认阈值、地图中心等。"""

    __tablename__ = "sys_config"

    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(128))
    group: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), default="string", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class OperationLog(Base, IdMixin):
    __tablename__ = "sys_operation_log"

    user_id: Mapped[int | None] = mapped_column(Integer)
    username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
