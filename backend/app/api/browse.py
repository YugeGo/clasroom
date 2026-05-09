"""
浏览模式 API — 校园 → 楼栋 → 教室 分层浏览

配合前端"浏览查找"模式使用，提供结构化数据导航。
数据源：import_data.py --to-json 导出的真实 JSON 文件。
"""
import re
from collections import defaultdict

from fastapi import APIRouter
from loguru import logger

from app.database.mock_data import _load_data

router = APIRouter(prefix="/api/browse", tags=["浏览"])


def _get_hierarchy():
    """从真实数据构建校园→楼栋→教室 树形结构"""
    data = _load_data()
    if not data:
        return {}

    # 按校区分组
    hierarchy: dict = defaultdict(lambda: defaultdict(set))

    for r in data:
        campus = r["campus"]
        name = r["room_name"]

        # 提取楼栋号
        if name[0].isdigit():
            if "-" in name:
                building = name.split("-")[0]  # "1-103" → "1"
            else:
                building = name[0]  # "1101" → "1"
        elif name.startswith("实验楼"):
            building = "实验楼"
        elif name.startswith("操场"):
            building = "操场"
        elif name.startswith("S") or name.startswith("Y") or name.startswith("wt"):
            building = name[:4] if len(name) > 4 else name
        else:
            building = name

        hierarchy[campus][building].add(name)

    # 转为可序列化结构
    result = {}
    for campus in sorted(hierarchy):
        buildings = {}
        for bld in sorted(hierarchy[campus]):
            buildings[bld] = sorted(hierarchy[campus][bld])
        result[campus] = buildings

    return result


@router.get("/campuses")
async def list_campuses():
    """获取所有校区列表，含每个校区的楼栋数"""
    h = _get_hierarchy()
    campuses = []
    for name in sorted(h):
        buildings = h[name]
        total_rooms = sum(len(rooms) for rooms in buildings.values())
        campuses.append({
            "name": name,
            "building_count": len(buildings),
            "room_count": total_rooms,
        })
    return {"campuses": campuses}


@router.get("/campuses/{campus}/buildings")
async def list_buildings(campus: str):
    """获取指定校区的楼栋列表"""
    h = _get_hierarchy()
    campus_data = h.get(campus)
    if not campus_data:
        return {"buildings": []}

    buildings = []
    for bld in sorted(campus_data):
        rooms = campus_data[bld]
        buildings.append({
            "name": bld,
            "display_name": _building_display_name(campus, bld),
            "room_count": len(rooms),
        })
    return {"campus": campus, "buildings": buildings}


@router.get("/campuses/{campus}/buildings/{building}/rooms")
async def list_rooms(campus: str, building: str):
    """获取指定楼栋的教室列表"""
    h = _get_hierarchy()
    rooms = (h.get(campus) or {}).get(building, [])
    return {
        "campus": campus,
        "building": building,
        "rooms": rooms,
    }


def _building_display_name(campus: str, bld: str) -> str:
    """生成楼栋显示名"""
    if bld.isdigit():
        return f"{bld}号楼"
    if bld == "实验楼":
        return "实验楼"
    if bld == "操场":
        return "操场"
    return bld
