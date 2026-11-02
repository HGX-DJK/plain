# -*- coding: utf-8 -*-
"""端到端冒烟测试：登录 -> 模块 -> 采集 -> 建筑物 -> 单位 -> 比对。"""
import sys

import httpx

BASE = "http://127.0.0.1:8100"
client = httpx.Client(base_url=BASE, timeout=30)


def main() -> int:
    r = client.post("/api/v1/login", json={"username": "admin", "password": "Admin@123"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    token = data["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    print("1. 登录 OK, user =", data["user"]["username"], "roles =", data["user"]["roles"])

    # 2. 信息模块
    r = client.post(
        "/api/v1/modules",
        json={
            "code": "YARD", "name": "院落", "geom_type": "polygon",
            "category": "面状要素", "color": "#f0a020",
            "fields": [
                {"key": "owner", "label": "产权人", "data_type": "string", "required": True, "searchable": True},
                {"key": "yard_area", "label": "占地面积(㎡)", "data_type": "number", "show_in_list": True},
                {"key": "usage", "label": "用途", "data_type": "select",
                 "options": [{"label": "居住", "value": "residence"}, {"label": "商用", "value": "business"}]},
            ],
        },
    )
    assert r.status_code == 200, r.text
    module_id = r.json()["data"]["id"]
    print("2. 信息模块 OK, module_id =", module_id, ", fields =", len(r.json()["data"]["fields"]))

    # 3. 采集要素（面）
    poly = {
        "type": "Polygon",
        "coordinates": [[
            [116.3970, 39.9080], [116.3980, 39.9080],
            [116.3980, 39.9090], [116.3970, 39.9090], [116.3970, 39.9080],
        ]],
    }
    r = client.post(
        "/api/v1/features",
        json={
            "module_id": module_id, "name": "张三家院落", "geometry": poly,
            "properties": {"owner": "张三", "yard_area": 320.5, "usage": "residence"},
            "declared_lng": 116.39750, "declared_lat": 39.90850,
        },
    )
    assert r.status_code == 200, r.text
    feat = r.json()["data"]
    print("3. 采集要素 OK, feature_id =", feat["id"], "| code =", feat["code"],
          "| center =", feat["center_lng"], feat["center_lat"], "| area =", feat["area_m2"], "㎡")

    # 4. 建筑物（面）
    r = client.post(
        "/api/v1/buildings",
        json={
            "code": "BLD-001", "name": "1号办公楼", "address": "某某路1号",
            "geometry": poly, "floor_count": 5, "building_height": 18.5,
            "structure_type": "框架", "usage": "办公", "status": "在用",
            "declared_lng": 116.3975, "declared_lat": 39.9085,
        },
    )
    assert r.status_code == 200, r.text
    bld = r.json()["data"]
    print("4. 建筑物 OK, building_id =", bld["id"], "| area =", bld["area_m2"], "㎡")

    # 5. 单位
    r = client.post(
        "/api/v1/units",
        json={
            "name": "某某科技有限公司", "credit_code": "91110000MA01TEST1X",
            "unit_type": "企业", "legal_person": "李四", "phone": "010-12345678",
            "address": "某某路1号", "geometry": {"type": "Point", "coordinates": [116.3975, 39.9085]},
        },
    )
    assert r.status_code == 200, r.text
    unit = r.json()["data"]
    print("5. 单位 OK, unit_id =", unit["id"])

    # 6. 关联
    r = client.post(
        f"/api/v1/buildings/{bld['id']}/units",
        json={"building_id": bld["id"], "unit_id": unit["id"], "relation_type": "产权", "is_primary": True},
    )
    assert r.status_code == 200, r.text
    print("6. 建筑-单位关联 OK")

    # 7. 比对（申报 vs 实测）
    r = client.post(
        "/api/v1/compare/tasks",
        json={"name": "第一次坐标比对", "source_type": "building", "threshold_m": 50.0},
    )
    assert r.status_code == 200, r.text
    task = r.json()["data"]
    print("7. 比对 OK, total =", task["summary"]["total"],
          "| passed =", task["summary"]["passed"], "| failed =", task["summary"]["failed"])

    # 8. 比对详情 + 地图数据
    r = client.get(f"/api/v1/compare/tasks/{task['id']}")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    print("8. 比对明细 OK, items =", len(items),
          "| 首条偏差 =", items[0]["deviation_m"], "m | 方位 =", items[0]["bearing_text"])

    r = client.get(f"/api/v1/compare/tasks/{task['id']}/map")
    m = r.json()["data"]
    print("   比对地图数据 OK, points =", len(m["points"]), ", lines =", len(m["lines"]))

    # 9. 非面几何拒收（面模块给点）
    r = client.post(
        "/api/v1/features",
        json={"module_id": module_id, "geometry": {"type": "Point", "coordinates": [116.39, 39.9]}},
    )
    assert r.status_code == 400, r.text
    print("9. 类型校验 OK ->", r.json()["message"])

    # 10. 工作台
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200, r.text
    s = r.json()["data"]
    print("10. 工作台 OK ->", {k: s[k] for k in ("module_total", "feature_total", "building_total", "unit_total")})

    print("\nALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
