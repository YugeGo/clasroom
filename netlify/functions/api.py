"""
Netlify Function — 山财空教室 API 后端

一个函数处理所有 /api/* 请求：
  POST /api/chat             — 自然语言查询空教室
  GET  /api/browse/campuses  — 校区列表
  GET  /api/browse/campuses/{campus}/buildings — 楼栋列表
  GET  /api/browse/campuses/{campus}/buildings/{building}/rooms — 教室列表

数据源：data/sdufe_rooms.json（由 import_data.py 生成）
"""
import json
import os
import re
from datetime import datetime

# ─── 数据加载 ───
_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "sdufe_rooms.json",
)

_cache = None


def _load_data():
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(_DATA_FILE):
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    else:
        _cache = []
    return _cache


# ─── 常量 ───
WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
CN_DIGITS = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
             "六": "6", "七": "7", "八": "8", "九": "9", "十": "10", "两": "2"}

TIME_KEYWORDS = {
    "上午": ["0102", "0304"], "中午": ["0506"], "下午": ["0506", "0708"],
    "晚上": ["0910"], "全天": ["0102", "0304", "0506", "0708", "0910"],
}
CAMPUS_KEYWORDS = {"舜耕": "舜耕", "燕山": "燕山", "章丘": "章丘", "圣井": "章丘"}
PERIOD_NUMS = {"1": "0102", "2": "0102", "3": "0304", "4": "0304",
               "5": "0506", "6": "0506", "7": "0708", "8": "0708",
               "9": "0910", "10": "0910"}

# 楼栋别名
BUILDING_ALIAS = {}
for n in range(1, 11):
    cn = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"][n - 1]
    for alias in [f"{n}号楼", f"{n}号教学楼", f"{cn}号楼", f"{cn}号教学楼",
                  f"第{cn}教学楼", f"{n}教", f"{cn}教"]:
        BUILDING_ALIAS[alias] = f"{n}号楼"


# ─── 意图解析（精简版） ───

def parse_intent(text):
    now = datetime.now()
    today_idx = now.weekday()
    text = text.strip()

    # 校区
    campus = None
    for kw, mapped in CAMPUS_KEYWORDS.items():
        if kw in text:
            campus = mapped
            break

    # 星期
    day_of_week = WEEKDAY_CN[today_idx]
    if "明天" in text:
        day_of_week = WEEKDAY_CN[(today_idx + 1) % 7]
    elif "后天" in text:
        day_of_week = WEEKDAY_CN[(today_idx + 2) % 7]
    else:
        m = re.search(r"(星期|周)([一二三四五六日])", text)
        if m:
            idx = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}.get(m.group(2))
            if idx is not None:
                day_of_week = WEEKDAY_CN[idx]

    # 节次
    period_slots = ["0102", "0304", "0506", "0708", "0910"]
    for kw, slots in TIME_KEYWORDS.items():
        if kw in text:
            period_slots = slots
            break

    range_match = re.search(r"第?(\d+)\s*[-–到至]\s*(\d+)\s*节", text)
    if range_match:
        slots = set()
        for n in range(int(range_match.group(1)), int(range_match.group(2)) + 1):
            if str(n) in PERIOD_NUMS:
                slots.add(PERIOD_NUMS[str(n)])
        if slots:
            period_slots = sorted(slots)

    cn_match = re.search(r"第?([一二三四五六七八九十两])[、]?([到至]?)([一二三四五六七八九十两]?)\s*节", text)
    if cn_match:
        cn_s, cn_e = CN_DIGITS.get(cn_match.group(1)), CN_DIGITS.get(cn_match.group(3) or cn_match.group(1))
        if cn_s and cn_e:
            slots = set()
            for n in range(int(cn_s), int(cn_e) + 1):
                if str(n) in PERIOD_NUMS:
                    slots.add(PERIOD_NUMS[str(n)])
            if slots:
                period_slots = sorted(slots)

    # 楼栋
    building = None
    for alias, std in sorted(BUILDING_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in text:
            building = std
            break

    # 教室号
    room = None
    room_match = re.search(r"(\d{1,2}[-]\d{3,4})", text)
    if room_match:
        room = room_match.group(1)
    else:
        room_match = re.search(r"(?<!\d)(\d{4})(?!\s*[节点])", text)
        if room_match:
            room = room_match.group(1)

    return {"campus": campus, "building": building, "room": room,
            "day_of_week": day_of_week, "period_slots": period_slots}


# ─── 数据筛选 ───

def query_rooms(campus, day_of_week, period_slots, building=None, room=None):
    data = _load_data()
    results = []

    bld_num = None
    if building:
        m = re.match(r"(\d+)号楼", building)
        if m:
            bld_num = m.group(1)

    for r in data:
        if campus and r["campus"] != campus:
            continue
        if r["day_of_week"] != day_of_week:
            continue
        if r["period_slot"] not in period_slots:
            continue
        if building:
            name = r["room_name"]
            if bld_num:
                if name[0].isdigit():
                    if not name.startswith(bld_num) and not name.startswith(f"{bld_num}-"):
                        continue
                elif name.startswith("实验楼") and bld_num == "6":
                    pass
                else:
                    continue
        if room and r["room_name"] != room:
            continue
        results.append(r)

    return results


# ─── 浏览数据 ───

def get_hierarchy():
    data = _load_data()
    h = {}
    for r in data:
        campus = r["campus"]
        name = r["room_name"]
        if name[0].isdigit():
            bld = name.split("-")[0] if "-" in name else name[0]
        elif name.startswith("实验楼"):
            bld = "实验楼"
        elif name.startswith("操场"):
            bld = "操场"
        else:
            bld = name
        h.setdefault(campus, {}).setdefault(bld, set()).add(name)

    result = {}
    for c in sorted(h):
        result[c] = {b: sorted(h[c][b]) for b in sorted(h[c])}
    return result


# ─── 请求处理 ───

def handle_chat(body):
    try:
        msg = json.loads(body).get("message", "")
    except Exception:
        return {"statusCode": 400, "body": json.dumps({"detail": "无效请求"})}

    intent = parse_intent(msg)
    rooms = query_rooms(
        campus=intent["campus"],
        day_of_week=intent["day_of_week"],
        period_slots=intent["period_slots"],
        building=intent["building"],
        room=intent["room"],
    )

    params = {"campus": intent["campus"], "building": intent["building"],
              "room": intent["room"], "day_of_week": intent["day_of_week"],
              "period_slots": intent["period_slots"]}

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "params": {k: v for k, v in params.items() if v is not None},
            "count": len(rooms),
            "rooms": [{"campus": r["campus"], "room_name": r["room_name"],
                       "day_of_week": r["day_of_week"], "period_slot": r["period_slot"]}
                      for r in rooms],
        }, ensure_ascii=False),
    }


def handle_browse(path):
    h = get_hierarchy()
    parts = path.rstrip("/").split("/")
    # parts = ["", "api", "browse", "campuses", ...]

    try:
        idx = parts.index("browse")
        args = parts[idx + 1:]  # ["campuses"] or ["campuses", "舜耕", "buildings"] etc.
    except ValueError:
        return {"statusCode": 404, "body": "Not found"}

    if args == ["campuses"]:
        campuses = []
        for name in sorted(h):
            blds = h[name]
            total_rooms = sum(len(rms) for rms in blds.values())
            campuses.append({"name": name, "building_count": len(blds), "room_count": total_rooms})
        return {"statusCode": 200, "body": json.dumps({"campuses": campuses}, ensure_ascii=False)}

    if len(args) >= 3 and args[1] == "buildings":
        campus = args[0]
        campus_data = h.get(campus, {})
        if len(args) >= 4 and args[2] == "buildings" and len(args) >= 5:
            building = args[3]
            rooms_list = campus_data.get(building, [])
            return {"statusCode": 200, "body": json.dumps(
                {"campus": campus, "building": building, "rooms": rooms_list}, ensure_ascii=False)}
        buildings = [{"name": b, "display_name": f"{b}号楼" if b.isdigit() else b,
                      "room_count": len(rms)} for b, rms in sorted(campus_data.items())]
        return {"statusCode": 200, "body": json.dumps(
            {"campus": campus, "buildings": buildings}, ensure_ascii=False)}

    return {"statusCode": 404, "body": "Not found"}


# ─── 入口 ───

def handler(event, context):
    path = event.get("path", "/")
    method = event.get("httpMethod", "GET")
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        if path.startswith("/api/chat"):
            result = handle_chat(event.get("body", "{}"))
        elif path.startswith("/api/browse"):
            result = handle_browse(path)
        else:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "Not found"})}

        result["headers"] = {**result.get("headers", {}), **headers}
        return result
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)}),
        }
