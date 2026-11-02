"""采集数据经纬度比对：申报坐标 vs 实测坐标。"""
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.session import Base
from app.models.common import IdMixin, TimestampMixin

# 比对数据来源
SOURCE_TYPES = ("feature", "building")


class ComparisonTask(Base, IdMixin, TimestampMixin):
    """一次比对批次：把同一来源的要素批量做申报/实测坐标核对。"""

    __tablename__ = "cmp_task"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    module_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta_info_module.id", ondelete="SET NULL")
    )
    threshold_m: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    source_ids: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["ComparisonItem"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )


class ComparisonItem(Base, IdMixin):
    """比对明细：一条记录的申报点、实测点、偏差与结论。"""

    __tablename__ = "cmp_item"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("cmp_task.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(255))
    declared_lng: Mapped[float | None] = mapped_column(Float)
    declared_lat: Mapped[float | None] = mapped_column(Float)
    measured_lng: Mapped[float | None] = mapped_column(Float)
    measured_lat: Mapped[float | None] = mapped_column(Float)
    # 两点几何，供前端地图直接绘制偏差连线
    declared_geom = mapped_column(Geometry("Point", srid=settings.spatial_srid), nullable=True)
    measured_geom = mapped_column(Geometry("Point", srid=settings.spatial_srid), nullable=True)
    deviation_m: Mapped[float | None] = mapped_column(Float)
    bearing_deg: Mapped[float | None] = mapped_column(Float)
    threshold_m: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    # ok / over_threshold / missing_declared / missing_geometry / invalid_coord
    issue: Mapped[str | None] = mapped_column(String(32))
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped[ComparisonTask] = relationship(back_populates="items")
