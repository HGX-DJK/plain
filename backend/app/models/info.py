"""信息模块（元数据驱动）+ 采集要素。

设计要点：先定义信息模块及其属性字段，前端按字段定义动态渲染表单，
采集到的属性值统一存放在 col_feature.properties（JSONB），
空间信息存放在 PostGIS 几何列，SRID 由 backend/.env 的 SPATIAL_SRID 决定（默认 4490）。
"""
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
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

# 信息模块支持的空间信息类型
GEOM_TYPES = ("point", "line", "polygon")
# 采集要素允许的 GeoJSON 几何类型
GEOJSON_TYPE_BY_GEOM = {
    "point": ("Point", "MultiPoint"),
    "line": ("LineString", "MultiLineString"),
    "polygon": ("Polygon", "MultiPolygon"),
}


class InfoModule(Base, IdMixin, TimestampMixin):
    """信息模块：一类可采集的地理实体（点/线/面）。"""

    __tablename__ = "meta_info_module"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    geom_type: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    color: Mapped[str] = mapped_column(String(16), default="#2d8cf0", nullable=False)
    icon: Mapped[str | None] = mapped_column(String(64))
    layer_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    editable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    fields: Mapped[list["InfoField"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="InfoField.sort_order",
        lazy="selectin",
    )


class InfoField(Base, IdMixin, TimestampMixin):
    """信息模块的属性字段定义。"""

    __tablename__ = "meta_info_field"
    __table_args__ = (
        UniqueConstraint("module_id", "key", name="uq_meta_info_field_key"),
    )

    module_id: Mapped[int] = mapped_column(
        ForeignKey("meta_info_module.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    # string / text / number / integer / date / datetime / select / multiselect / boolean / coordinate
    data_type: Mapped[str] = mapped_column(String(24), default="string", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unique_value: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON)
    default_value: Mapped[str | None] = mapped_column(String(255))
    placeholder: Mapped[str | None] = mapped_column(String(255))
    help_text: Mapped[str | None] = mapped_column(String(255))
    validation: Mapped[dict | None] = mapped_column(JSON)
    show_in_list: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    searchable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    module: Mapped[InfoModule] = relationship(back_populates="fields")


class Feature(Base, IdMixin, TimestampMixin):
    """采集要素：某个信息模块下的一条空间+属性记录。"""

    __tablename__ = "col_feature"
    __table_args__ = (
        UniqueConstraint("code", name="uq_col_feature_code"),
        # 地图按模块聚合取数、列表按模块过滤都要先按 module_id 收窄，
        # 没有这个索引时每次查询都会全表扫（col_feature 已超 47 万行）。
        # 空间索引 idx_col_feature_geometry 由 GeoAlchemy2 的 Geometry(spatial_index=True) 自动建。
        Index("idx_col_feature_module", "module_id"),
    )

    module_id: Mapped[int] = mapped_column(
        ForeignKey("meta_info_module.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(255))
    # 几何类型（点/线/面）由所属信息模块决定，写入前在服务层校验
    geometry = mapped_column(Geometry("GEOMETRY", srid=settings.spatial_srid), nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSON)
    # 申报坐标：由上报/设计资料录入，用于与实测（绘制）坐标比对
    declared_lng: Mapped[float | None] = mapped_column(Float)
    declared_lat: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    module: Mapped[InfoModule] = relationship(lazy="selectin")
