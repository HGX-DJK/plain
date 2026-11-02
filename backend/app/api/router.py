"""API 路由汇总。"""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    buildings,
    compare,
    configs,
    dashboard,
    facade,
    features,
    modules,
    roles,
    units,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(modules.router)
api_router.include_router(features.router)
api_router.include_router(buildings.router)
api_router.include_router(facade.router)
api_router.include_router(units.router)
api_router.include_router(compare.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(configs.router)
