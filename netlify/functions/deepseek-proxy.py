"""
Netlify Function — DeepSeek API 代理

在浏览器端不便暴露 API Key，通过此函数中转：
  前端 → /.netlify/functions/deepseek-proxy → DeepSeek API → 返回结果
"""
import json
import os
from urllib import request as url_req, error as url_err

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

# ─── System Prompt（同 app/ai/deepseek.py） ───
from datetime import datetime
WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
PERIOD_LABELS = {
    "0102": "第1-2节 (08:00-09:35)", "0304": "第3-4节 (09:50-11:25)",
    "0506": "第5-6节 (13:30-15:05)", "0708": "第7-8节 (15:20-16:55)",
    "0910": "第9-10节 (18:30-20:05)",
}


def build_system_prompt():
    now = datetime.now()
    weekday = WEEKDAY_CN[now.weekday()]
    time_str = f"{now.year}年{now.month}月{now.day}日 {weekday} {now.hour:02d}:{now.minute:02d}"
    slots_desc = "、".join(f"'{k}'={v}" for k, v in PERIOD_LABELS.items())
    return (
        f"你是一个山财空教室意图解析器。当前系统时间：{time_str}。"
        "将用户的自然语言转化为 JSON。必须映射为山财的黑话：\n\n"
        "* campus (string|null): 仅限 ['舜耕', '燕山', '章丘']，未提则为 null。"
        "若用户说「圣井」，自动映射为「章丘」；若说「明水」，视为 null。\n"
        "* day_of_week (string): 格式 '星期一'~'星期日'。"
        "如用户说「明天」，根据当前时间推算。\n"
        "* period_slots (array): 可选值：" + slots_desc + "。"
        "'上午'=['0102','0304']，'下午'=['0506','0708']，'晚上'=['0910']。\n\n"
        "请只输出 JSON。"
    )


def handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Content-Type": "application/json",
    }

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    if event.get("httpMethod") != "POST":
        return {"statusCode": 405, "headers": headers,
                "body": json.dumps({"error": "Method not allowed"})}

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "DEEPSEEK_API_KEY not configured",
                                    "fallback": True})}

    try:
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", "")
        prompt_type = body.get("type", "parse")  # "parse" or "summarize"
        context_data = body.get("context", "")
    except Exception:
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid request body"})}

    # 构建消息
    if prompt_type == "parse":
        system = build_system_prompt()
        user = message
    elif prompt_type == "summarize":
        system = "你是一个山财空教室助手。将查询结果用一段自然语言总结给用户，要友好、简洁、有温度。"
        user = f"用户问题：{message}\n\n查询结果：{context_data}"
    else:
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Unknown type"})}

    # 调用 DeepSeek API
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object" if prompt_type == "parse" else "text"},
        "temperature": 0.1 if prompt_type == "parse" else 0.7,
        "max_tokens": 512,
    }).encode("utf-8")

    req = url_req.Request(
        DEEPSEEK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        resp = url_req.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]

        if prompt_type == "parse":
            # 解析 JSON
            parsed = json.loads(content)
            return {"statusCode": 200, "headers": headers,
                    "body": json.dumps({"intent": parsed})}
        else:
            return {"statusCode": 200, "headers": headers,
                    "body": json.dumps({"summary": content})}

    except url_err.HTTPError as e:
        err_body = e.read().decode()
        return {"statusCode": e.code, "headers": headers,
                "body": json.dumps({"error": f"DeepSeek API error: {err_body}",
                                    "fallback": True})}
    except Exception as e:
        return {"statusCode": 500, "headers": headers,
                "body": json.dumps({"error": str(e), "fallback": True})}
