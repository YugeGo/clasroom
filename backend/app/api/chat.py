"""
空教室查询核心接口 — POST /api/chat

流程:
  用户自然语言 → DeepSeek JSON Mode 意图解析 → 数据库查询 → 结构化 JSON 返回

遵循架构文档规范。

MOCK_MODE:
  当 config.MOCK_MODE = True 时，使用关键词匹配 + 内存数据模拟完整流程，
  无需 PostgreSQL 和 DeepSeek API，方便开发调试。
"""
import json as _json
import urllib.request as _req
import urllib.error as _err

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.ai.deepseek import intent_parser
from app.database.models import SdufeFreeRoom
from app.database.session import get_optional_db

router = APIRouter(prefix="/api", tags=["空教室查询"])


# ──────────────────────────────────────────────
# 请求 / 响应模型
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户自然语言查询")


class QueryParams(BaseModel):
    campus: str | None = Field(None, description="校区: 舜耕/燕山/章丘")
    building: str | None = Field(None, description="楼栋: 3号楼/7号楼")
    room: str | None = Field(None, description="具体教室: 1101/7-116")
    day_of_week: str = Field(..., description="星期: 星期一~星期日")
    period_slots: list[str] = Field(..., description="节次: 0102/0304/0506/0708/0910")


class RoomSlot(BaseModel):
    campus: str
    room_name: str
    day_of_week: str
    period_slot: str


class ChatResponse(BaseModel):
    params: QueryParams
    count: int
    rooms: list[RoomSlot]


# ──────────────────────────────────────────────
# 核心接口
# ──────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat_query(
    request: ChatRequest,
    db: AsyncSession | None = Depends(get_optional_db),
):
    """
    核心查询接口。

    接收自然语言消息 → 解析意图 → 查询空教室 → 返回结果。
    """
    user_message = request.message.strip()
    logger.info(f"[POST /api/chat] 收到消息: {user_message[:60]}")

    # ─── MOCK 模式：无需数据库和 API Key ───
    if settings.MOCK_MODE:
        from app.database.mock_data import mock_chat_response
        result = mock_chat_response(user_message)
        if result is None:
            raise HTTPException(status_code=400, detail="无法理解您的查询。")
        logger.info(f"[Mock] {result['count']} 间空教室")
        return ChatResponse(
            params=QueryParams(**result["params"]),
            count=result["count"],
            rooms=[RoomSlot(**r) for r in result["rooms"]],
        )

    # ─── 生产模式：DeepSeek + PostgreSQL ───
    # Step 1: DeepSeek 意图解析
    intent = await intent_parser.parse(user_message)
    if intent is None:
        raise HTTPException(
            status_code=400,
            detail="无法理解您的查询，请重新描述。例如：「下午舜耕有空教室吗？」",
        )

    # Step 2: 构建数据库查询
    query = select(SdufeFreeRoom).where(
        SdufeFreeRoom.day_of_week == intent["day_of_week"],
        SdufeFreeRoom.period_slot.in_(intent["period_slots"]),
    )

    if intent.get("campus"):
        query = query.where(SdufeFreeRoom.campus == intent["campus"])

    query = query.order_by(SdufeFreeRoom.room_name, SdufeFreeRoom.period_slot)
    logger.info(f"SQL: day={intent['day_of_week']}, "
                f"slots={intent['period_slots']}, "
                f"campus={intent.get('campus', 'ALL')}")

    # Step 3: 执行查询
    result = await db.execute(query)
    rows = result.scalars().all()

    rooms = [
        RoomSlot(
            campus=r.campus,
            room_name=r.room_name,
            day_of_week=r.day_of_week,
            period_slot=r.period_slot,
        )
        for r in rows
    ]

    # Step 4: 构建响应
    params = QueryParams(
        campus=intent.get("campus"),
        day_of_week=intent["day_of_week"],
        period_slots=intent["period_slots"],
    )

    logger.info(f"查询结果: {len(rooms)} 间空教室")
    return ChatResponse(
        params=params,
        count=len(rooms),
        rooms=rooms,
    )


# ─── DeepSeek 代理（供前端本地开发用，生产环境走 Netlify Function） ───

class DeepSeekRequest(BaseModel):
    message: str
    type: str = "parse"
    context: str = ""


@router.post("/deepseek")
async def deepseek_proxy(request: DeepSeekRequest):
    """
    DeepSeek API 代理 — 本地开发时前端通过此接口调用 DeepSeek。
    生产环境生产环境由 netlify/functions/deepseek-proxy.py 处理。
    """
    api_key = settings.LLM_API_KEY
    if not api_key:
        from app.ai.mock_intent import parse_mock_intent
        from app.database.mock_data import mock_chat_response

        if request.type == "parse":
            intent = parse_mock_intent(request.message)
            return {"intent": intent, "fallback": True}
        return {"summary": None, "fallback": True}

    # 构建 system prompt
    now = datetime.now()
    wd = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    ts = f"{now.year}年{now.month}月{now.day}日 {wd[now.weekday()]}"
    slots_desc = "、".join(f"'{k}'={v}" for k, v in settings.SDUFE_PERIOD_SLOTS.items())

    if request.type == "parse":
        system = (
            f"你是一个山财空教室意图解析器。当前系统时间：{ts}。"
            "将用户的自然语言转化为 JSON。必须映射为山财的黑话：\n\n"
            "* campus (string|null): 仅限 ['舜耕', '燕山', '章丘']"
            "，未提则为 null。若用户说「圣井」，自动映射为「章丘」。\n"
            "* day_of_week (string): 格式 '星期一'~'星期日'。\n"
            "* period_slots (array): 可选值：" + slots_desc + "。"
            "'上午'=['0102','0304']，'下午'=['0506','0708']。\n"
        )
        user = request.message
    else:
        system = "你是一个山财空教室助手。将查询结果用一段自然语言总结给用户。"
        user = f"用户问题：{request.message}\n\n查询结果：{request.context}"

    payload = _json.dumps({
        "model": settings.LLM_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object" if request.type == "parse" else "text"},
        "temperature": 0.1 if request.type == "parse" else 0.7,
        "max_tokens": 512,
    }).encode()

    req = _req.Request(
        f"{settings.LLM_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        resp = _req.urlopen(req, timeout=30)
        result = _json.loads(resp.read())
        content = result["choices"][0]["message"]["content"]

        if request.type == "parse":
            return {"intent": _json.loads(content)}
        return {"summary": content}
    except Exception as e:
        return {"error": str(e), "fallback": True}
