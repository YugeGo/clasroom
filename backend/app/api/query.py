"""
空教室查询 API — 接收自然语言查询，返回流式响应 (SSE)
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.ai.intent import IntentParser, QueryParams
from app.config import settings
from app.database.models import Room, Schedule, Building
from app.database.session import get_db

router = APIRouter(prefix="/api/query", tags=["查询"])


@router.post("/chat")
async def chat_query(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    主查询接口：接收用户消息，返回 SSE 流式响应

    请求体: {"message": "我现在在3号楼，找个没人的教室待到下午5点"}
    响应: SSE 事件流，包含 意图解析 → 数据库查询 → 结果包装 三个阶段
    """
    user_message = request.get("message", "").strip()
    if not user_message:
        return {"error": "消息不能为空"}

    intent_parser = IntentParser()

    async def event_generator():
        # Step 1: 意图解析
        yield {"event": "phase", "data": json.dumps({"phase": "parsing", "message": "🤔 正在理解你的需求..."})}

        params = await intent_parser.parse(user_message)
        if params is None:
            yield {"event": "error", "data": json.dumps({"error": "无法理解您的查询，请重新描述"})}
            return

        yield {
            "event": "intent",
            "data": json.dumps({
                "phase": "parsed",
                "params": params.to_dict(),
                "message": f"📌 查询条件: {'、'.join(_build_query_summary(params))}",
            }),
        }

        # Step 2: 数据库查询
        yield {"event": "phase", "data": json.dumps({"phase": "querying", "message": "🔍 正在搜索空教室..."})}

        results = await _query_empty_rooms(db, params)
        logger.info(f"查询到 {len(results)} 间空教室")

        # Step 3: 结果输出（先发结构化数据）
        yield {
            "event": "result",
            "data": json.dumps({
                "phase": "result",
                "count": len(results),
                "rooms": results,
            }),
        }

        # Step 4: LLM 包装自然语言回复
        yield {"event": "phase", "data": json.dumps({"phase": "wrapping", "message": "✍️ 正在整理回复..."})}

        reply = await intent_parser.wrap_response(results, user_message)
        yield {"event": "reply", "data": json.dumps({"phase": "done", "reply": reply})}

    return EventSourceResponse(event_generator())


@router.post("/rooms")  # Simple alternative without streaming
async def query_rooms(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """简化的非流式查询接口，直接返回 JSON 数据"""
    user_message = request.get("message", "").strip()
    if not user_message:
        return {"error": "消息不能为空"}

    intent_parser = IntentParser()
    params = await intent_parser.parse(user_message)
    if params is None:
        return {"error": "无法解析查询意图", "rooms": []}

    results = await _query_empty_rooms(db, params)
    reply = await intent_parser.wrap_response(results, user_message)

    return {
        "params": params.to_dict(),
        "count": len(results),
        "rooms": results,
        "reply": reply,
    }


# ──────────────────────────────────────────────
# 内部查询引擎
# ──────────────────────────────────────────────

async def _query_empty_rooms(
    db: AsyncSession,
    params: QueryParams,
) -> list[dict]:
    """
    核心空教室查询逻辑

    思路：
      SELECT * FROM rooms WHERE room_id NOT IN (
        SELECT room_id FROM schedules
        WHERE day_of_week = :day
          AND start_period <= :end_p
          AND end_period >= :start_p
      ) AND building_name = :building (可选)
    """
    start_p = _time_to_period(params.start_time)
    end_p = _time_to_period(params.end_time)

    # 如果没有转换到有效节次，使用保守范围
    if start_p is None:
        start_p = 1
    if end_p is None:
        end_p = 13

    logger.info(f"时间段映射: {params.start_time}-{params.end_time} → 第{start_p}-{end_p}节")

    # 子查询: 在该时间段有课的教室
    occupied_subq = (
        select(Schedule.room_id)
        .where(
            Schedule.day_of_week == params.day_of_week,
            Schedule.start_period <= end_p,
            Schedule.end_period >= start_p,
            Schedule.is_active == True,
        )
        .subquery()
    )

    # 主查询: rooms NOT IN occupied
    query = (
        select(Room, Building)
        .join(Building, Room.building_id == Building.id)
        .where(
            Room.is_active == True,
            Room.id.not_in(occupied_subq),
        )
        .order_by(Building.name, Room.room_number)
    )

    if params.building:
        query = query.where(Building.name.contains(params.building.replace("教", "号楼")))

    if params.min_capacity:
        query = query.where(Room.capacity >= params.min_capacity)

    if params.floor:
        # 从 room_number 推断楼层（通常第一位数字）
        query = query.where(Room.floor == params.floor)

    result = await db.execute(query)
    rows = result.all()

    output = []
    for room, building in rows:
        output.append({
            "room_id": room.id,
            "building_name": building.name,
            "room_number": room.room_number,
            "floor": room.floor or _guess_floor(room.room_number),
            "capacity": room.capacity,
            "room_type": room.room_type,
        })

    return output


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _time_to_period(time_str: str) -> Optional[int]:
    """将 HH:MM 时间映射到教务系统节次 (1-13)"""
    try:
        t = datetime.strptime(time_str, "%H:%M")
        total_minutes = t.hour * 60 + t.minute
    except (ValueError, TypeError):
        return None

    # 遍历节次映射找到最匹配的
    for period_num, (start_str, end_str) in settings.PERIOD_MAP.items():
        s_h, s_m = map(int, start_str.split(":"))
        e_h, e_m = map(int, end_str.split(":"))
        s_min = s_h * 60 + s_m
        e_min = e_h * 60 + e_m
        mid_min = (s_min + e_min) // 2

        if total_minutes <= mid_min:
            return int(period_num)

    return 13


def _guess_floor(room_number: str) -> int:
    """从教室号推断楼层（如 '402' → 4 楼）"""
    if room_number and len(room_number) >= 3:
        try:
            return int(room_number[0])
        except ValueError:
            pass
    return 0


def _build_query_summary(params: QueryParams) -> list[str]:
    """构建人类可读的查询条件摘要"""
    parts = []
    if params.building:
        parts.append(params.building)
    parts.append(f"周{_day_cn(params.day_of_week)}")
    parts.append(f"{params.start_time}-{params.end_time}")
    if params.min_capacity:
        parts.append(f"≥{params.min_capacity}人")
    if params.floor:
        parts.append(f"{params.floor}楼")
    return parts


def _day_cn(d: int) -> str:
    return ["", "一", "二", "三", "四", "五", "六", "日"][d] if 1 <= d <= 7 else "?"
