"""
公开 API — 供其他项目调用的空教室查询接口

保持原有 web 应用不变，额外提供 RESTful API。
"""
from fastapi import APIRouter, Query
from loguru import logger

from app.database.mock_data import _load_data

router = APIRouter(prefix="/api/v1", tags=["公开 API"])


@router.get("/rooms")
async def get_free_rooms(
    campus: str = Query(None, description="校区：舜耕/燕山/章丘"),
    day: str = Query(None, description="星期：星期一~星期日，默认今天"),
    period: str = Query(None, description="节次：0102/0304/0506/0708/0910，多个用逗号分隔"),
    building: str = Query(None, description="楼栋关键词：3号楼/实验楼"),
    floor: int = Query(None, description="楼层：1-9"),
):
    """获取符合条件的空闲教室列表"""
    data = _load_data()
    if not data:
        return {"code": 0, "data": [], "total": 0}

    from datetime import datetime
    WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    today = WEEKDAY_CN[(datetime.now().weekday() + 1) % 7]
    if day is None:
        day = today

    period_slots = period.split(",") if period else ["0102", "0304", "0506", "0708", "0910"]

    results = []
    for r in data:
        if campus and r["campus"] != campus:
            continue
        if r["day_of_week"] != day:
            continue
        if r["period_slot"] not in period_slots:
            continue
        if building and building not in r["room_name"]:
            continue
        if floor is not None:
            name = r["room_name"]
            if "-" in name:
                f = int(name.split("-")[1][0])
            elif len(name) == 4 and name.isdigit():
                f = int(name[1])
            else:
                f = 0
            if f != floor:
                continue
        results.append(r)

    return {"code": 0, "data": results, "total": len(results)}


@router.get("/campuses")
async def list_campuses():
    """获取校区列表"""
    data = _load_data()
    campuses = {}
    for r in data:
        campuses.setdefault(r["campus"], set()).add(r["room_name"])

    items = []
    for name in sorted(campuses):
        items.append({
            "name": name,
            "room_count": len(campuses[name]),
        })
    return {"code": 0, "data": items}


@router.get("/rooms/{room_name}/schedule")
async def get_room_schedule(room_name: str, campus: str = Query(None)):
    """获取指定教室的周课表（空闲时段）"""
    data = _load_data()
    all_slots = ["0102", "0304", "0506", "0708", "0910"]
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    free_set = set()
    for r in data:
        if r["room_name"] == room_name and (not campus or r["campus"] == campus):
            free_set.add(f"{r['day_of_week']}|{r['period_slot']}")

    schedule = []
    for day in weekdays:
        slots = []
        for slot in all_slots:
            slots.append({
                "period": slot,
                "free": f"{day}|{slot}" in free_set,
            })
        schedule.append({"day": day, "slots": slots})

    return {
        "code": 0,
        "data": {
            "room_name": room_name,
            "campus": next((r["campus"] for r in data if r["room_name"] == room_name), ""),
            "schedule": schedule,
        },
    }


@router.get("/status")
async def api_status():
    """API 状态"""
    data = _load_data()
    return {
        "code": 0,
        "data": {
            "name": "山财自习通 API",
            "version": "1.0.0",
            "total_records": len(data),
            "campuses": list(set(r["campus"] for r in data)),
        },
    }
