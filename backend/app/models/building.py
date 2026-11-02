"""建筑物基础数据采集 + 建筑物所在单位信息采集。"""
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.session import Base
from app.models.common import IdMixin, TimestampMixin

BUILDING_STATUS = ("在用", "闲置", "在建", "已拆除", "其他")
UNIT_RELATION_TYPES = ("产权", "使用", "管理", "经营", "其他")


class Building(Base, IdMixin, TimestampMixin):
    """建筑物基础数据：必须为面状空间信息。"""

    __tablename__ = "bld_building"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(512))
    parcel_code: Mapped[str | None] = mapped_column(String(64))
    region_code: Mapped[str | None] = mapped_column(String(64))
    geometry = mapped_column(Geometry("Polygon", srid=settings.spatial_srid), nullable=False)
    # 申报坐标：设计/上报资料的经纬度，与实测（面中心）比对
    declared_lng: Mapped[float | None] = mapped_column(Float)
    declared_lat: Mapped[float | None] = mapped_column(Float)
    floor_count: Mapped[int | None] = mapped_column(Integer)
    building_height: Mapped[float | None] = mapped_column(Float)
    usage: Mapped[str | None] = mapped_column(String(64))
    structure_type: Mapped[str | None] = mapped_column(String(64))
    build_year: Mapped[int | None] = mapped_column(Integer)
    ownership: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="在用", nullable=False)
    attachments: Mapped[list | None] = mapped_column(JSON)
    extra: Mapped[dict | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))


class Unit(Base, IdMixin, TimestampMixin):
    """单位（法人/组织）信息。"""

    __tablename__ = "org_unit"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credit_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    unit_type: Mapped[str | None] = mapped_column(String(64))
    legal_person: Mapped[str | None] = mapped_column(String(64))
    contact_name: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(128))
    address: Mapped[str | None] = mapped_column(String(512))
    geometry = mapped_column(Geometry("Point", srid=settings.spatial_srid), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    buildings: Mapped[list["BuildingUnit"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan", lazy="selectin"
    )


class BuildingUnit(Base, IdMixin, TimestampMixin):
    """建筑物与单位的关联关系（多对多）。"""

    __tablename__ = "rel_building_unit"
    __table_args__ = (
        UniqueConstraint(
            "building_id", "unit_id", "relation_type", name="uq_rel_building_unit"
        ),
    )

    building_id: Mapped[int] = mapped_column(
        ForeignKey("bld_building.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("org_unit.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(16), default="使用", nullable=False)
    share_ratio: Mapped[float | None] = mapped_column(Float)
    start_date: Mapped[str | None] = mapped_column(String(32))
    end_date: Mapped[str | None] = mapped_column(String(32))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    building: Mapped[Building] = relationship(lazy="selectin")
    unit: Mapped[Unit] = relationship(back_populates="buildings", lazy="selectin")
