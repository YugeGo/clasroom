"""
AI 意图解析引擎

使用大模型的 Function Calling / Tool Use 能力，将用户自然语言
转化为结构化的空教室查询参数。
"""
import json
from datetime import datetime
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

from app.ai.prompts import QUERY_TOOL_DEFINITION, SYSTEM_PROMPT
from app.config import settings


class QueryParams:
    """LLM 提取出的结构化查询参数"""

    def __init__(
        self,
        building: Optional[str] = None,
        start_time: str = "08:00",
        end_time: str = "22:00",
        day_of_week: Optional[int] = None,
        min_capacity: Optional[int] = None,
        floor: Optional[int] = None,
        raw_query: str = "",
    ):
        self.building = building
        self.start_time = start_time
        self.end_time = end_time
        self.day_of_week = day_of_week or datetime.now().isoweekday()
        self.min_capacity = min_capacity
        self.floor = floor
        self.raw_query = raw_query

    def to_dict(self) -> dict:
        return {
            "building": self.building,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "day_of_week": self.day_of_week,
            "min_capacity": self.min_capacity,
            "floor": self.floor,
        }


class IntentParser:
    """意图解析器 — 将自然语言 → 结构化查询参数"""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY or settings.OPENAI_API_KEY,
                base_url=settings.LLM_BASE_URL or settings.OPENAI_BASE_URL,
            )
        return self._client

    async def parse(self, user_input: str) -> Optional[QueryParams]:
        """
        调用 LLM Function Calling 解析用户输入

        返回 QueryParams，解析失败则返回 None
        """
        logger.info(f"意图解析: {user_input[:50]}...")
        client = self._get_client()

        try:
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                tools=[QUERY_TOOL_DEFINITION],
                tool_choice="auto",
                temperature=0.1,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return None

        message = response.choices[0].message

        if not message.tool_calls:
            logger.warning("LLM 未调用工具")
            return None

        # 解析第一个 tool call
        tool_call = message.tool_calls[0]
        args_raw = tool_call.function.arguments
        logger.info(f"LLM 返回参数: {args_raw}")

        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            logger.error(f"LLM 返回 JSON 解析失败: {args_raw}")
            return None

        return QueryParams(
            building=args.get("building"),
            start_time=args.get("start_time", "08:00"),
            end_time=args.get("end_time", "22:00"),
            day_of_week=args.get("day_of_week", datetime.now().isoweekday()),
            min_capacity=args.get("min_capacity"),
            floor=args.get("floor"),
            raw_query=user_input,
        )

    async def wrap_response(self, results: list[dict], user_query: str) -> str:
        """
        让 LLM 将查询结果包装成自然语言回复
        如果 LLM 调用失败，返回格式化的纯文本回退内容
        """
        if not results:
            return self._fallback_empty(user_query)

        client = self._get_client()
        results_json = json.dumps(results, ensure_ascii=False, indent=2)

        try:
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"用户的问题是: {user_query}\n\n"
                            f"你查询到以下空教室数据:\n{results_json}\n\n"
                            "请将数据整理成一段自然友好的回复，按楼栋分组列出空教室。"
                        ),
                    },
                ],
                temperature=0.7,
                max_tokens=512,
            )
            return response.choices[0].message.content or self._fallback_text(results)
        except Exception as e:
            logger.warning(f"LLM 包装回复失败: {e}")
            return self._fallback_text(results)

    @staticmethod
    def _fallback_text(results: list[dict]) -> str:
        """纯文本回退：当 LLM 包装失败时使用"""
        if not results:
            return "😅 很抱歉，没有找到符合条件的空教室。试试换个时间或教学楼？"

        # 按楼栋分组
        by_building = {}
        for r in results:
            bld = r.get("building_name", "未知")
            by_building.setdefault(bld, []).append(r)

        lines = [f"🔍 找到 {len(results)} 间空教室：\n"]
        for bld, rooms in by_building.items():
            lines.append(f"📚 {bld}:")
            for r in rooms:
                cap = f" ({r.get('capacity', '?')}人)" if r.get("capacity") else ""
                floor_info = f"{r.get('floor', '?')}楼" if r.get("floor") else ""
                lines.append(f"  • {r['room_number']}室 {floor_info}{cap}")
            lines.append("")

        lines.append("💡 建议早点去占座，热门教室很快就会被占满哦！")
        return "\n".join(lines)

    @staticmethod
    def _fallback_empty(query: str) -> str:
        return (
            f"😅 我查了一下，按照「{query[:30]}」的条件，"
            f"目前没有找到可用的空教室。\n\n"
            f"💡 建议：\n"
            f"  • 换个时间段试试\n"
            f"  • 换个教学楼\n"
            f"  • 看看其他楼层的教室"
        )
