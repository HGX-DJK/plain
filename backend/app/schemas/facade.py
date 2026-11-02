"""建筑物外景影像的出入参。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FacadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    building_id: int
    kind: str
    facade: str
    floor_no: int | None = None
    file_name: str
    file_path: str
    thumb_path: str | None = None
    mime: str | None = None
    file_size: int
    width: int | None = None
    height: int | None = None
    taken_at: datetime | None = None
    lng: float | None = None
    lat: float | None = None
    uploader_name: str | None = None
    remark: str | None = None
    extra: dict[str, Any] | None = None
    is_primary: bool = False
    created_at: datetime


class FacadeUpdate(BaseModel):
    facade: str | None = None
    floor_no: int | None = None
    taken_at: datetime | None = None
    remark: str | None = None
    lng: float | None = None
    lat: float | None = None
    is_primary: bool | None = None


class FacadeStats(BaseModel):
    total: int
    by_facade: dict[str, int]
    by_kind: dict[str, int]
    cover_url: str | None = None
