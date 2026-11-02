"""建筑物外景影像：外景照片 / 360 全景图 / 三维模型文件。"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import IdMixin, TimestampMixin

# 立面方位
FACADE_DIRECTIONS: dict[str, str] = {
    "east": "东立面",
    "south": "南立面",
    "west": "西立面",
    "north": "北立面",
    "top": "屋顶",
    "other": "其他",
}

# 影像类别
FACADE_KINDS: dict[str, str] = {
    "photo": "外景照片",
    "panorama": "全景图",
    "model": "三维模型",
}


class FacadeMedia(Base, IdMixin, TimestampMixin):
    """一条外景影像记录，实物文件落在 uploads/facade 下。"""

    __tablename__ = "bld_facade_media"
    __table_args__ = (
        Index("ix_bld_facade_media_building", "building_id", "kind"),
        Index("ix_bld_facade_media_facade", "facade"),
    )

    building_id: Mapped[int] = mapped_column(
        ForeignKey("bld_building.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="photo")
    facade: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    floor_no: Mapped[int | None] = mapped_column(Integer)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumb_path: Mapped[str | None] = mapped_column(String(512))
    mime: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lng: Mapped[float | None] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float)

    uploader_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))
    uploader_name: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON)

    # 是否作为该建筑的封面图
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
