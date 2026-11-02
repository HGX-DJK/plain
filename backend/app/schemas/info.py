"""信息模块、属性字段、采集要素。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.info import GEOM_TYPES


class FieldUpsert(BaseModel):
    id: int | None = None
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    data_type: str = "string"
    required: bool = False
    unique_value: bool = False
    options: list[dict] | None = None
    default_value: str | None = None
    placeholder: str | None = None
    help_text: str | None = None
    validation: dict | None = None
    show_in_list: bool = True
    searchable: bool = False
    sort_order: int = 0


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    key: str
    label: str
    data_type: str
    required: bool
    unique_value: bool
    options: list[dict] | None = None
    default_value: str | None = None
    placeholder: str | None = None
    help_text: str | None = None
    validation: dict | None = None
    show_in_list: bool
    searchable: bool
    sort_order: int


class ModuleUpsert(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    geom_type: str
    category: str | None = None
    color: str = "#2d8cf0"
    icon: str | None = None
    layer_order: int = 0
    editable: bool = True
    is_active: bool = True
    description: str | None = None
    fields: list[FieldUpsert] = []

    @field_validator("geom_type")
    @classmethod
    def _check_geom_type(cls, v: str) -> str:
        if v not in GEOM_TYPES:
            raise ValueError(f"geom_type 必须是 {'/'.join(GEOM_TYPES)}")
        return v


class ModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    geom_type: str
    category: str | None = None
    color: str
    icon: str | None = None
    layer_order: int
    editable: bool
    is_active: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    fields: list[FieldOut] = []
    feature_count: int | None = None


class ModuleBriefOut(BaseModel):
    """图层列表用的精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    geom_type: str
    color: str
    layer_order: int
    is_active: bool


class FeatureUpsert(BaseModel):
    module_id: int
    code: str | None = None
    name: str | None = None
    geometry: Any
    properties: dict = {}
    declared_lng: float | None = None
    declared_lat: float | None = None
    status: str = "draft"
    remark: str | None = None


class FeatureUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    geometry: Any | None = None
    properties: dict | None = None
    declared_lng: float | None = None
    declared_lat: float | None = None
    status: str | None = None
    remark: str | None = None


class FeatureOut(BaseModel):
    id: int
    module_id: int
    module_name: str | None = None
    code: str | None = None
    name: str | None = None
    geometry: Any | None = None
    properties: dict | None = None
    declared_lng: float | None = None
    declared_lat: float | None = None
    center_lng: float | None = None
    center_lat: float | None = None
    area_m2: float | None = None
    length_m: float | None = None
    status: str
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class FeatureMapOut(BaseModel):
    """地图渲染用的精简要素（GeoJSON Feature）。"""

    id: int
    module_id: int
    code: str | None = None
    name: str | None = None
    geometry: Any
    properties: dict
