"""
大模型提示词模板 (Prompts)

包含系统提示词、Function Calling 定义、以及自然语言回复包装器。
"""

SYSTEM_PROMPT = """你是一位智能的空教室查询助手，部署在高校教务系统中。

你的职责：
1. 理解用户用自然语言表达的空教室查询需求
2. 调用 `query_empty_rooms` 函数提取结构化查询参数
3. 根据查询结果，用亲切自然的语言回复用户

注意事项：
- 如果用户没有指定教学楼，可以默认查询所有教学楼
- 如果用户没有指定时间，默认查询当前时间之后
- 如果用户提到的教学楼名称在系统中不完全匹配，尝试推断（如 "3教" -> "3号楼"）
- 回复要简洁友好，提供教室编号、楼层和座位数信息
- 若查询结果为空，给用户建设性建议（换个时间、换个楼等）
"""

QUERY_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "query_empty_rooms",
        "description": "根据用户自然语言查询，提取空教室检索参数",
        "parameters": {
            "type": "object",
            "properties": {
                "building": {
                    "type": "string",
                    "description": "教学楼名称，如 '3号楼'、'第二教学楼'。如果用户说'3教'、'三教'，请规范为'3号楼'",
                },
                "start_time": {
                    "type": "string",
                    "description": "查询起始时间，格式 HH:MM，24小时制。如 '14:00'",
                },
                "end_time": {
                    "type": "string",
                    "description": "查询结束时间，格式 HH:MM，24小时制。如 '17:00'",
                },
                "day_of_week": {
                    "type": "integer",
                    "description": "星期几，1=周一，2=周二，3=周三，4=周四，5=周五，6=周六，7=周日。默认今天",
                    "minimum": 1,
                    "maximum": 7,
                },
                "min_capacity": {
                    "type": "integer",
                    "description": "最少座位数，用户提及'大教室'默认100人以上，'小教室'默认30人以下",
                },
                "floor": {
                    "type": "integer",
                    "description": "指定楼层，如用户说'3楼'则填3",
                },
            },
            "required": ["start_time", "end_time"],
        },
    },
}

RESPONSE_TEMPLATE = """查询结果：找到 {count} 间空教室

{building_info}{time_info}

{room_list}

{tip}
"""

QUERY_CONTEXT_PROMPT = """你查询到以下空教室数据：

{results_json}

请将这些数据整理成一段自然、友好的回复。要求：
1. 先告诉用户一共找到几间空教室
2. 按教学楼分组列出空教室（每个教室一行）
3. 每间教室提供：教室号、楼层、座位数
4. 结尾给一个实用小建议（如"建议早点去占座"）
5. 保持简洁，不要啰嗦
"""
