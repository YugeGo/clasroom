"""
Mock 意图解析器 — 关键词匹配，无需调用 DeepSeek API

开发/演示用，模拟自然语言 → 结构化查询参数的解析过程。
"""
import re
from datetime import datetime
from typing import Optional

from loguru import logger

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 常见口语 → 节次映射
TIME_KEYWORDS: dict[str, list[str]] = {
    "上午": ["0102", "0304"],
    "中午": ["0506"],
    "下午": ["0506", "0708"],
    "晚上": ["0910"],
    "全天": ["0102", "0304", "0506", "0708", "0910"],
    "早": ["0102", "0304"],
    "午": ["0506", "0708"],
    "晚": ["0910"],
}

# 校区关键词
CAMPUS_KEYWORDS: dict[str, str] = {
    "舜耕": "舜耕",
    "燕山": "燕山",
    "章丘": "章丘",
    "圣井": "章丘",
    "明水": "__skip__",
}

# 中文数字 → 阿拉伯数字映射
CN_DIGITS = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
             "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
             "两": "2"}

# 节次数字映射
PERIOD_NUMS: dict[str, str] = {
    "1": "0102", "2": "0102",
    "3": "0304", "4": "0304",
    "5": "0506", "6": "0506",
    "7": "0708", "8": "0708",
    "9": "0910", "10": "0910",
}

# 楼栋名称规范化：各种用户输入 → 标准楼栋名
BUILDING_ALIAS: dict[str, str] = {}
_for_bld_aliases: list[tuple[str, int]] = []
# 自动生成 1-10 号楼的别名
for n in range(1, 11):
    cn = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"][n - 1]
    BUILDING_ALIAS[f"{n}号楼"] = f"{n}号楼"
    BUILDING_ALIAS[f"{n}号教学楼"] = f"{n}号楼"
    BUILDING_ALIAS[f"{cn}号楼"] = f"{n}号楼"
    BUILDING_ALIAS[f"{cn}号教学楼"] = f"{n}号楼"
    BUILDING_ALIAS[f"第{cn}教学楼"] = f"{n}号楼"
    BUILDING_ALIAS[f"第{n}教学楼"] = f"{n}号楼"
    BUILDING_ALIAS[f"{n}教"] = f"{n}号楼"
    BUILDING_ALIAS[f"{cn}教"] = f"{n}号楼"


def parse_mock_intent(user_input: str) -> Optional[dict]:
    """
    通过关键词匹配解析用户意图，模拟 DeepSeek JSON Mode 输出。
    """
    text = user_input.strip()
    now = datetime.now()
    today_idx = now.weekday()  # 0=星期一

    # 1. 解析校区
    campus = None
    for keyword, mapped in CAMPUS_KEYWORDS.items():
        if keyword in text:
            if mapped == "__skip__":
                campus = None
            else:
                campus = mapped
            break

    # 2. 解析星期
    day_of_week = WEEKDAY_CN[today_idx]
    if any(w in text for w in ["今天", "现在"]):
        day_of_week = WEEKDAY_CN[today_idx]
    elif "明天" in text:
        day_of_week = WEEKDAY_CN[(today_idx + 1) % 7]
    elif "后天" in text:
        day_of_week = WEEKDAY_CN[(today_idx + 2) % 7]
    elif "昨天" in text:
        day_of_week = WEEKDAY_CN[(today_idx - 1) % 7]
    else:
        # 尝试匹配"星期X"或"周X"
        day_match = re.search(r"(星期|周)([一二三四五六日])", text)
        if day_match:
            day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}
            idx = day_map.get(day_match.group(2))
            if idx is not None:
                day_of_week = WEEKDAY_CN[idx]

    # 3. 解析节次
    period_slots = list(TIME_KEYWORDS.get("全天"))

    # 检查具体节次数字
    period_nums_found = re.findall(r"(\d+)\s*(?:节|点)", text)
    if period_nums_found:
        slots = set()
        for n in period_nums_found:
            if n in PERIOD_NUMS:
                slots.add(PERIOD_NUMS[n])
        if slots:
            period_slots = sorted(slots)

    # 检查口语时段
    for keyword, slots in TIME_KEYWORDS.items():
        if keyword in text:
            period_slots = slots
            break

    # 检查"第X-Y节"格式（阿拉伯数字，必须含"节"字，防止误配教室号如"7-116"）
    range_match = re.search(r"第?(\d+)\s*[-–到至]\s*(\d+)\s*节", text)
    if range_match:
        start, end = int(range_match.group(1)), int(range_match.group(2))
        slots = set()
        for n in range(start, end + 1):
            if str(n) in PERIOD_NUMS:
                slots.add(PERIOD_NUMS[str(n)])
        if slots:
            period_slots = sorted(slots)

    # 检查中文数字节次：
    #   "三四节" → 3,4节 → ["0304"]
    #   "第三四节" / "第三、四节" → 同上
    #   "五到七节" → 5,6,7节 → ["0506", "0708"]
    # 匹配两个独立的中文数字（中间可选 、或到至）
    cn_period_match = re.search(
        r"第?([一二三四五六七八九十两])[、]?([到至]?)([一二三四五六七八九十两]?)\s*节", text
    )
    if cn_period_match:
        g1, g2, g3 = cn_period_match.groups()
        logger.debug(f"[CnPeriod] matched: groups=({g1},{g2},{g3})")
        cn_start = CN_DIGITS.get(g1)
        cn_end = CN_DIGITS.get(g3 or g1)
        if cn_start and cn_end:
            start_n, end_n = int(cn_start), int(cn_end)
            slots = set()
            for n in range(start_n, end_n + 1):
                if str(n) in PERIOD_NUMS:
                    slots.add(PERIOD_NUMS[str(n)])
            if slots:
                logger.debug(f"[CnPeriod] {start_n}-{end_n}节 → {slots}")
                period_slots = sorted(slots)

    # 4. 解析楼栋名称
    building = None
    # 先尝试精确匹配（长匹配优先）
    matched_alias = None
    for alias, std_name in sorted(BUILDING_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in text:
            matched_alias = std_name
            break
    if matched_alias:
        building = matched_alias

    # 5. 解析具体教室号
    room = None
    # 章丘格式 "7-116"、"1-103"（在 campus/building 关键词之后）
    room_match = re.search(r"(?:号楼|教学楼)?[-]?(\d{1,2}[-]\d{3,4})", text)
    if room_match:
        room = room_match.group(1)
    else:
        # 舜耕/燕山 4位教室号: "1101", "3104"（但不是时间 "1点2节"）
        room_match = re.search(r"(?<!\d)(\d{4})(?!\s*[节点])", text)
        if room_match:
            room = room_match.group(1)
        # 实验楼
        if not room:
            room_match = re.search(r"(实验楼\d+)", text)
            if room_match:
                room = room_match.group(1)

    result = {
        "campus": campus,
        "building": building,
        "room": room,
        "day_of_week": day_of_week,
        "period_slots": period_slots,
    }
    logger.info(f"[MockIntent] '{user_input[:60]}' → {result}")
    return result
