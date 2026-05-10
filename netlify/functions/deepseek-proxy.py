"""Netlify Function — DeepSeek API 代理"""
import json, os
from urllib import request, error

def handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Content-Type": "application/json",
    }
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    api_key = os.environ.get("VITE_DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "API Key not configured", "fallback": True})}

    try:
        body = json.loads(event.get("body", "{}"))
    except:
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid body"})}

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": body.get("messages", []),
        "response_format": body.get("response_format"),
        "temperature": body.get("temperature", 0.1),
        "max_tokens": 512,
    }).encode()

    req = request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        resp = request.urlopen(req, timeout=30)
        return {"statusCode": 200, "headers": headers,
                "body": resp.read().decode()}
    except error.HTTPError as e:
        return {"statusCode": e.code, "headers": headers,
                "body": json.dumps({"error": e.read().decode(), "fallback": True})}
