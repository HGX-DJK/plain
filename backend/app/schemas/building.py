"""建筑物、单位、关联，以及经纬度比对。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------- 建筑物 ----------------
class BuildingUpsert(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    address: str | None = None
    parcel_code: str | None = None
    region_code: str | None = None
    geometry: Any
    declared_lng: float | None = None
    declared_lat: float | None = None
    floor_count: int | None = None
    building_height: float | None = None
    usage: str | None = None
    structure_type: str | None = None
    build_year: int | None = None
    ownership: str | None = None
    status: str = "在用"
    attachments: list | None = None
    extra: dict | None = None
    remark: str | None = None


class BuildingOut(BaseModel):
    id: int
    code: str
    name: str
    address: str | None = None
    parcel_code: str | None = None
    region_code: str | None = None
    geometry: Any | None = None
    declared_lng: float | None = None
    declared_lat: float | None = None
    center_lng: float | None = None
    center_lat: float | None = None
    area_m2: float | None = None
    floor_count: int | None = None
    building_height: float | None = None
    usage: str | None = None
    structure_type: str | None = None
    build_year: int | None = None
    ownership: str | None = None
    status: str
    attachments: list | None = None
    extra: dict | None = None
    remark: str | None = None
    created_at: datetime
    updated_at: datetime
    units: list["UnitBriefInBuilding"] = []


class UnitBriefInBuilding(BaseModel):
    """建筑物详情里嵌的单位摘要。"""

    relation_id: int
    unit_id: int
    name: str
    credit_code: str | None = None
    relation_type: str
    share_ratio: float | None = None
    is_primary: bool


# ---------------- 单位 ----------------
class UnitUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    credit_code: str | None = None
    unit_type: str | None = None
    legal_person: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    geometry: Any | None = None
    remark: str | None = None


class UnitOut(BaseModel):
    id: int
    name: str
    credit_code: str | None = None
    unit_type: str | None = None
    legal_person: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    geometry: Any | None = None
    remark: str | None = None
    created_at: datetime
    building_count: int | None = None


class BuildingUnitUpsert(BaseModel):
    building_id: int
    unit_id: int
    relation_type: str = "使用"
    share_ratio: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_primary: bool = False
    remark: str | None = None


class BuildingUnitOut(BaseModel):
    id: int
    building_id: int
    unit_id: int
    relation_type: str
    share_ratio: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_primary: bool
    remark: str | None = None
    building_name: str | None = None
    building_code: str | None = None
    unit_name: str | None = None
    unit_credit_code: str | None = None


BuildingOut.model_rebuild()


# ---------------- 经纬度比对 ----------------
class ComparisonTaskUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: str = "feature"
    module_id: int | None = None
    threshold_m: float = 10.0
    description: str | None = None
    # 为空则比对该来源下的全部记录
    source_ids: list[int] = []


class ComparisonItemOut(BaseModel):
    id: int
    task_id: int
    source_type: str
    source_id: int
    code: str | None = None
    name: str | None = None
    declared_lng: float | None = None
    declared_lat: float | None = None
    measured_lng: float | None = None
    measured_lat: float | None = None
    declared_geom: Any | None = None
    measured_geom: Any | None = None
    deviation_m: float | None = None
    bearing_deg: float | None = None
    threshold_m: float | None = None
    passed: bool | None = None
    issue: str | None = None
    remark: str | None = None


class ComparisonTaskOut(BaseModel):
    id: int
    name: str
    source_type: str
    module_id: int | None = None
    module_name: str | None = None
    threshold_m: float
    status: str
    total_count: int
    passed_count: int
    failed_count: int
    description: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class ComparisonTaskDetailOut(ComparisonTaskOut):
    items: list[ComparisonItemOut] = []


class ComparisonItemUpdate(BaseModel):
    remark: str | None = None
