"""用户、角色、权限、系统参数。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str | None = None
    phone: str | None = None
    email: str | None = None
    dept: str | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    roles: list[str] = []
    permissions: list[str] = []


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    real_name: str | None = None
    phone: str | None = None
    email: str | None = None
    dept: str | None = None
    is_active: bool = True
    remark: str | None = None
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    password: str | None = Field(None, min_length=6, max_length=128)
    real_name: str | None = None
    phone: str | None = None
    email: str | None = None
    dept: str | None = None
    is_active: bool | None = None
    remark: str | None = None
    role_ids: list[int] | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None
    is_builtin: bool
    created_at: datetime
    permission_ids: list[int] = []


class RoleUpsert(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[int] = []


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    module: str
    action: str | None = None
    perm_type: str
    sort_order: int


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str | None = None
    label: str | None = None
    group: str
    value_type: str
    description: str | None = None


class ConfigUpsert(BaseModel):
    key: str
    value: str | None = None
    label: str | None = None
    group: str = "general"
    value_type: str = "string"
    description: str | None = None


class RolePermissionsUpdate(BaseModel):
    permission_ids: list[int]
