"""
DeepSeek JSON Mode 意图解析器

使用 DeepSeek API（通过 OpenAI SDK 兼容调用）的 JSON Mode 功能，
将用户自然语言 → 结构化空教室查询参数。

架构文档指定的解析流程：
  用户输入 → DeepSeek JSON Mode → 意图 JSON → 数据库查询 → 结果
"""
import json
from datetime import datetime
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

from app.config import settings

# 架构文档指定的星期映射
WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 节次时段口语化映射（供 LLM 参考）
PERIOD_SLOT_LABELS = {
    "0102": "第1-2节 (08:00-09:35)",
    "0304": "第3-4节 (09:50-11:25)",
    "0506": "第5-6节 (13:30-15:05)",
    "0708": "第7-8节 (15:20-16:55)",
    "0910": "第9-10节 (18:30-20:05)",
}


def _build_system_prompt() -> str:
    """构建 DeepSeek System Prompt，注入当前时间"""
    now = datetime.now()
    weekday = WEEKDAY_CN[now.weekday()]
    time_str = f"{now.year}年{now.month}月{now.day}日 {weekday} {now.hour:02d}:{now.minute:02d}"

    slots_desc = "、".join(
        f"'{k}'={v}" for k, v in PERIOD_SLOT_LABELS.items()
    )

    return (
        f"你是一个山财空教室意图解析器。当前系统时间：{time_str}。 "
        "将用户的自然语言转化为 JSON。必须映射为山财的黑话：\n\n"
        "* campus (string|null): 仅限 ['舜耕', '燕山', '章丘']，未提则为 null。"
        "【向下兼容规则】：若用户说「圣井」，自动映射为「章丘」；若说「明水」，视为 null。\n"
        "* day_of_week (string): 格式必须为 '星期一' 到 '星期日'。"
        "如用户说「明天」，请根据当前时间推算；说「后天」同样推算。\n"
        "* period_slots (array): 必须映射为教务系统格式。可选值："
        + slots_desc
        + "。例如「上午」=['0102', '0304']，"
        "「下午」=['0506', '0708']，"
        "「晚上」=['0910']，「全天」=所有节次。\n\n"
        "请只输出 JSON，不要包含任何其他文字。"
    )


# DeepSeek expected output schema (for validation)
EXPECTED_FIELDS = {"campus", "day_of_week", "period_slots"}


class DeepSeekIntentParser:
    """意图解析器 — 调用 DeepSeek JSON Mode 提取结构化参数"""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._today: Optional[datetime] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = settings.LLM_API_KEY
            if not api_key:
                raise ValueError(
                    "LLM_API_KEY 未配置。请在 .env 中设置 DeepSeek API Key。"
                )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.LLM_BASE_URL or "https://api.deepseek.com",
            )
        return self._client

    async def parse(self, user_input: str) -> Optional[dict]:
        """
        调用 DeepSeek JSON Mode 解析用户输入。

        返回结构化意图 dict，解析失败返回 None。
        返回值示例:
            {"campus": "舜耕", "day_of_week": "星期五", "period_slots": ["0506", "0708"]}
        """
        user_input = user_input.strip()
        if not user_input:
            logger.warning("用户输入为空")
            return None

        system_prompt = _build_system_prompt()
        logger.info(f"[DeepSeek] 解析输入: '{user_input[:60]}...'")

        client = self._get_client()

        try:
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,  # deepseek-chat
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=512,
            )
        except Exception as e:
            logger.error(f"[DeepSeek] API 调用失败: {e}")
            return None

        content = response.choices[0].message.content
        if not content:
            logger.warning("[DeepSeek] 返回空内容")
            return None

        logger.info(f"[DeepSeek] 原始返回: {content[:200]}")

        # 解析 JSON
        try:
            intent = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"[DeepSeek] JSON 解析失败: {e}, content={content}")
            return None

        # 验证 + 修复
        intent = self._validate_intent(intent)
        if intent is None:
            logger.warning("[DeepSeek] 意图验证未通过")
            return None

        logger.info(f"[DeepSeek] 解析结果: campus={intent['campus']}, "
                     f"day={intent['day_of_week']}, slots={intent['period_slots']}")
        return intent

    def _validate_intent(self, intent: dict) -> Optional[dict]:
        """验证并修复 DeepSeek 返回的 JSON"""
        if not isinstance(intent, dict):
            logger.warning(f"意图不是 dict: {type(intent)}")
            return None

        # 检查必需字段
        missing = EXPECTED_FIELDS - set(intent.keys())
        if missing:
            logger.warning(f"意图缺少字段: {missing}")
            return None

        # 修复 campus
        campus = intent.get("campus")
        if campus and campus not in settings.SDUFE_CAMPUSES:
            # 尝试模糊匹配
            for valid in settings.SDUFE_CAMPUSES:
                if valid in campus or campus in valid:
                    campus = valid
                    break
            else:
                campus = None
        intent["campus"] = campus  # None → null

        # 修复 day_of_week
        day = intent.get("day_of_week", "")
        if day and day not in WEEKDAY_CN:
            # 尝试映射 "周X" → "星期X"
            for i, wd in enumerate(WEEKDAY_CN, 1):
                if str(i) in day or wd[1:] in day:
                    day = wd
                    break
            else:
                # 回退到今天
                now = datetime.now()
                day = WEEKDAY_CN[now.weekday()]
                logger.info(f"day_of_week 回退到今天: {day}")
        intent["day_of_week"] = day

        # 修复 period_slots
        slots = intent.get("period_slots", [])
        if not isinstance(slots, list):
            slots = [slots] if isinstance(slots, str) else []
        valid_slots = list(settings.SDUFE_PERIOD_SLOTS.keys())
        slots = [s for s in slots if s in valid_slots]
        if not slots:
            # 默认全部节次
            slots = valid_slots
            logger.info(f"period_slots 为空，使用全部节次: {slots}")
        intent["period_slots"] = slots

        return intent


# 单例
intent_parser = DeepSeekIntentParser()
