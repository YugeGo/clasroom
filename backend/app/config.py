"""
全局配置模块
通过环境变量覆盖默认值，生产环境请使用 .env 文件
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ─── 服务配置 ───
    APP_NAME: str = "山财自习通"
    DEBUG: bool = True
    MOCK_MODE: bool = True   # True=无需数据库和 API Key，返回示例数据

    # ─── 数据库 ───
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/campus_rooms"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── 教务系统配置 ───
    # 教务系统类型: zhengfang | qiangzhi | urp | custom
    EDU_SYSTEM_TYPE: str = "zhengfang"
    EDU_BASE_URL: str = "http://jwxt.example.edu.cn"
    EDU_LOGIN_PATH: str = "/login"
    EDU_CAPTCHA_PATH: str = "/captcha"
    EDU_SCHEDULE_PATH: str = "/schedule"

    # 测试账号（仅在 DEBUG 模式下使用）
    EDU_USERNAME: str = ""
    EDU_PASSWORD: str = ""

    # ─── 验证码识别 ───
    # local: ddddocr | openai: GPT-4o Vision | third-party: 第三方打码平台
    CAPTCHA_SOLVER: str = "local"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    CAPTCHA_THIRD_PARTY_URL: str = ""
    CAPTCHA_THIRD_PARTY_KEY: str = ""

    # ─── 爬虫调度 ───
    SYNC_CRON: str = "0 3 * * *"       # 每天凌晨3点同步
    COOKIE_TTL_SECONDS: int = 1800      # Cookie 有效期30分钟
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3

    # ─── AI / LLM (DeepSeek) ───
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"
    LLM_MAX_TOKENS: int = 1024

    # ─── 山财校区配置 ───
    SDUFE_CAMPUSES: list[str] = ["舜耕", "燕山", "章丘"]

    # ─── 节次映射（山财教务系统格式） ───
    SDUFE_PERIOD_SLOTS: dict[str, str] = {
        "0102": "第1-2节",
        "0304": "第3-4节",
        "0506": "第5-6节",
        "0708": "第7-8节",
        "0910": "第9-10节",
    }
    SDUFE_PERIOD_TIME_MAP: dict[str, tuple[str, str]] = {
        "0102": ("08:00", "09:35"),
        "0304": ("09:50", "11:25"),
        "0506": ("13:30", "15:05"),
        "0708": ("15:20", "16:55"),
        "0910": ("18:30", "20:05"),
    }

    # ─── 爬虫（保留兼容，实际清洗入库走 sdufe_free_rooms） ───
    BUILDINGS: list[str] = [
        "1号楼", "2号楼", "3号楼", "4号楼", "5号楼",
        "6号楼", "7号楼", "8号楼", "9号楼", "10号楼",
    ]
    PERIOD_MAP: dict[str, tuple[str, str]] = {
        "1": ("08:00", "08:45"),
        "2": ("08:50", "09:35"),
        "3": ("09:50", "10:35"),
        "4": ("10:40", "11:25"),
        "5": ("11:30", "12:15"),
        "6": ("13:30", "14:15"),
        "7": ("14:20", "15:05"),
        "8": ("15:20", "16:05"),
        "9": ("16:10", "16:55"),
        "10": ("17:00", "17:45"),
        "11": ("18:30", "19:15"),
        "12": ("19:20", "20:05"),
        "13": ("20:10", "20:55"),
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
