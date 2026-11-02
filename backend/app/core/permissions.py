"""权限码字典：既是接口依赖的依据，也是初始化种子和前端菜单/按钮门控的依据。

perm_type=menu 的前端菜单权限，code 以 menu: 开头；其余为动作权限。
"""
from typing import TypedDict


class PermDef(TypedDict):
    code: str
    name: str
    module: str
    action: str | None
    perm_type: str


def _a(code: str, name: str, module: str, action: str) -> PermDef:
    return {
        "code": f"{module}:{code}",
        "name": name,
        "module": module,
        "action": action,
        "perm_type": "action",
    }


def _m(code: str, name: str) -> PermDef:
    return {
        "code": f"menu:{code}",
        "name": name,
        "module": f"menu:{code}",
        "action": None,
        "perm_type": "menu",
    }


MENUS: list[PermDef] = [
    _m("dashboard", "工作台"),
    _m("module", "信息模块管理"),
    _m("collect", "数据采集"),
    _m("building", "建筑物采集"),
    _m("facade", "建筑物外景"),
    _m("unit", "单位信息采集"),
    _m("compare", "经纬度比对"),
    _m("system", "系统设置"),
]

ACTIONS: list[PermDef] = [
    # 信息模块
    _a("view", "查看信息模块", "module", "view"),
    _a("create", "新增信息模块", "module", "create"),
    _a("update", "编辑信息模块", "module", "update"),
    _a("delete", "删除信息模块", "module", "delete"),
    # 采集要素
    _a("view", "查看采集数据", "feature", "view"),
    _a("create", "新增采集数据", "feature", "create"),
    _a("update", "编辑采集数据", "feature", "update"),
    _a("delete", "删除采集数据", "feature", "delete"),
    _a("export", "导出采集数据", "feature", "export"),
    # 建筑物
    _a("view", "查看建筑物", "building", "view"),
    _a("create", "新增建筑物", "building", "create"),
    _a("update", "编辑建筑物", "building", "update"),
    _a("delete", "删除建筑物", "building", "delete"),
    # 建筑物外景影像
    _a("view", "查看外景影像", "facade", "view"),
    _a("create", "上传外景影像", "facade", "create"),
    _a("update", "编辑外景影像", "facade", "update"),
    _a("delete", "删除外景影像", "facade", "delete"),
    # 单位
    _a("view", "查看单位", "unit", "view"),
    _a("create", "新增单位", "unit", "create"),
    _a("update", "编辑单位", "unit", "update"),
    _a("delete", "删除单位", "unit", "delete"),
    _a("link", "维护建筑-单位关联", "unit", "link"),
    # 比对
    _a("view", "查看比对结果", "compare", "view"),
    _a("run", "发起比对任务", "compare", "run"),
    _a("delete", "删除比对任务", "compare", "delete"),
    _a("export", "导出比对结果", "compare", "export"),
    # 系统设置
    _a("view", "查看用户与角色", "system", "view"),
    _a("user", "维护用户", "system", "user"),
    _a("role", "维护角色与权限", "system", "role"),
    _a("config", "维护系统参数", "system", "config"),
]

ALL_PERMISSIONS: list[PermDef] = MENUS + ACTIONS

# 内置角色及其权限范围（super_admin 拥有全部，代码里直接放行）
BUILTIN_ROLES: dict[str, dict] = {
    "super_admin": {
        "name": "超级管理员",
        "description": "系统全部权限",
        "permissions": None,
    },
    "collector": {
        "name": "采集员",
        "description": "现场采集与自查询",
        "permissions": [
            "menu:dashboard",
            "menu:collect",
            "menu:building",
            "menu:facade",
            "menu:unit",
            "module:view",
            "feature:view",
            "feature:create",
            "feature:update",
            "building:view",
            "building:create",
            "building:update",
            "facade:view",
            "facade:create",
            "facade:update",
            "unit:view",
            "unit:create",
            "unit:update",
            "unit:link",
            "compare:view",
        ],
    },
    "auditor": {
        "name": "审核员",
        "description": "数据复核与比对",
        "permissions": [
            "menu:dashboard",
            "menu:module",
            "menu:collect",
            "menu:building",
            "menu:facade",
            "menu:unit",
            "menu:compare",
            "module:view",
            "feature:view",
            "feature:update",
            "feature:export",
            "building:view",
            "facade:view",
            "facade:update",
            "facade:delete",
            "unit:view",
            "compare:view",
            "compare:run",
            "compare:export",
        ],
    },
    "viewer": {
        "name": "只读用户",
        "description": "仅查看",
        "permissions": [
            "menu:dashboard",
            "menu:collect",
            "menu:building",
            "menu:facade",
            "menu:compare",
            "module:view",
            "feature:view",
            "building:view",
            "facade:view",
            "unit:view",
            "compare:view",
        ],
    },
}
