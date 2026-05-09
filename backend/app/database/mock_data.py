"""
Mock 数据 — 加载真实山财课表解析结果（JSON）

当没有 PostgreSQL 时，从 import_data.py --to-json 导出的 JSON 文件
加载真实课表数据，替代数据库查询。
"""
import json
import os
import re
from typing import Optional

from loguru import logger

from app.ai.mock_intent import parse_mock_intent

# 项目根目录（backend/ 的父目录）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# JSON 数据文件路径（由 import_data.py --to-json 生成）
DATA_FILE = os.path.join(os.path.dirname(_PROJECT_ROOT), "data", "sdufe_rooms.json")

# 内存缓存
_cache: Optional[list[dict]] = None


def _load_data() -> list[dict]:
    """从 JSON 文件加载真实教室数据"""
    global _cache
    if _cache is not None:
        return _cache

    if not os.path.exists(DATA_FILE):
        logger.warning(f"数据文件不存在: {DATA_FILE}")
        logger.warning("请先运行: python -m scripts.import_data --to-json ../data/sdufe_rooms.json")
        _cache = []
        return _cache

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        _cache = json.load(f)

    logger.info(f"已加载 {len(_cache)} 条真实教室数据 ({DATA_FILE})")
    return _cache


def get_rooms(
    campus: str | None,
    day_of_week: str,
    period_slots: list[str],
    building: str | None = None,
    room: str | None = None,
) -> list[dict]:
    """
    从真实数据中筛选符合条件的空教室记录。
    """
    all_data = _load_data()
    if not all_data:
        return []

    results = []

    # 楼栋号提取（"3号楼" → "3"）
    bld_num = None
    if building:
        m = re.match(r"(\d+)号楼", building)
        if m:
            bld_num = m.group(1)

    for r in all_data:
        # 校区筛选
        if campus and r["campus"] != campus:
            continue

        # 星期筛选
        if r["day_of_week"] != day_of_week:
            continue

        # 节次筛选
        if r["period_slot"] not in period_slots:
            continue

        # 楼栋筛选：适配真实命名规则
        if building:
            name = r["room_name"]
            if bld_num:
                if name[0].isdigit():
                    if not name.startswith(bld_num) and not name.startswith(f"{bld_num}-"):
                        continue
                elif name.startswith("实验楼") and bld_num == "6":
                    pass  # 实验楼 = 6号楼
                else:
                    continue
            else:
                if building not in name:
                    continue

        # 具体教室号筛选
        if room and r["room_name"] != room:
            continue

        results.append(r)

    return results


def mock_chat_response(user_message: str) -> Optional[dict]:
    """
    Mock 模式下处理聊天请求的入口。
    使用真实课表数据（来自 JSON），返回与 /api/chat 一致的响应结构。
    """
    intent = parse_mock_intent(user_message)
    if intent is None:
        return None

    rooms = get_rooms(
        campus=intent.get("campus"),
        day_of_week=intent["day_of_week"],
        period_slots=intent["period_slots"],
        building=intent.get("building"),
        room=intent.get("room"),
    )

    params = {
        "campus": intent.get("campus"),
        "day_of_week": intent["day_of_week"],
        "period_slots": intent["period_slots"],
    }
    if intent.get("building"):
        params["building"] = intent["building"]
    if intent.get("room"):
        params["room"] = intent["room"]

    return {
        "params": params,
        "count": len(rooms),
        "rooms": rooms,
    }
