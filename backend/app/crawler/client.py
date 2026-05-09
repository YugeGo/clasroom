"""
教务系统模拟登录爬虫客户端 (EduSystemClient)

支持常见的正方、强智、URP 等教务系统登录流程:
  1. GET 登录页 → 提取隐藏表单域 (VIEWSTATE, Execution, csrf 等)
  2. GET 验证码图片 → 识别
  3. POST 登录表单 (账号+密码+验证码+隐藏域) → 获取 Cookie
  4. 携带 Cookie 请求课表页面 → 解析

架构特点:
  - 使用 httpx.Client 保持 Cookie 会话
  - 自动探测教务系统类型并适配登录流程
  - 验证码识别可插拔 (OCR / AI Vision / 第三方)
  - 完整重试与异常处理
"""
import re
import asyncio
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.config import settings
from app.crawler.captcha import CaptchaSolver


class EduSystemClient:
    """教务系统客户端 — 模拟登录 + 数据抓取"""

    def __init__(self, base_url: str = "", system_type: str = ""):
        self.base_url = base_url or settings.EDU_BASE_URL.rstrip("/")
        self.system_type = system_type or settings.EDU_SYSTEM_TYPE
        self.captcha_solver = CaptchaSolver()

        # 带 Cookie 持久化的 HTTP 会话
        self._http = httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.REQUEST_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            },
        )
        self._cookies: dict[str, str] = {}
        self._logged_in = False

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    async def login(self, username: str = "", password: str = "") -> bool:
        """完整的模拟登录流程"""
        username = username or settings.EDU_USERNAME
        password = password or settings.EDU_PASSWORD
        if not username or not password:
            logger.error("未配置教务系统账号密码")
            return False

        logger.info(f"开始登录教务系统 [{self.system_type}] {self.base_url}")

        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                return await self._attempt_login(username, password)
            except Exception as e:
                logger.warning(f"登录尝试 {attempt}/{settings.MAX_RETRIES} 失败: {e}")
                if attempt < settings.MAX_RETRIES:
                    wait = attempt * 2
                    logger.info(f"{wait} 秒后重试...")
                    await asyncio.sleep(wait)

        logger.error("登录失败，已达最大重试次数")
        return False

    async def fetch_schedule_page(
        self,
        building: str = "",
        room: str = "",
        semester: str = "",
    ) -> Optional[str]:
        """获取指定教室/楼栋的课表页面 HTML"""
        if not self._logged_in:
            logger.error("未登录，无法获取课表")
            return None

        url = self._build_schedule_url(building, room, semester)
        logger.info(f"正在抓取课表: {url}")

        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
            logger.info(f"课表页面获取成功 (状态码={resp.status_code})")
            return resp.text
        except Exception as e:
            logger.error(f"课表抓取失败: {e}")
            return None

    async def fetch_all_schedules(self) -> dict[str, str]:
        """遍历所有教学楼/教室抓取课表，返回 {教室标识: HTML}"""
        results = {}
        for building in settings.BUILDINGS:
            html = await self.fetch_schedule_page(building=building)
            if html:
                results[building] = html
            # 礼貌间隔，避免触发反爬
            await asyncio.sleep(1.5)
        return results

    async def close(self):
        await self._http.aclose()

    # ──────────────────────────────────────────────
    # 内部登录流程
    # ──────────────────────────────────────────────

    async def _attempt_login(self, username: str, password: str) -> bool:
        """单次登录尝试"""
        # Step 1: 获取登录页 & 隐藏字段
        hidden_fields = await self._fetch_login_page()
        if hidden_fields is None:
            return False

        # Step 2: 获取并识别验证码
        captcha_text = await self._resolve_captcha()
        if captcha_text is None and self._captcha_is_mandatory():
            logger.error("验证码识别失败（必填）")
            return False

        # Step 3: 构造登录表单
        form_data = self._build_login_form(
            username, password, captcha_text or "", hidden_fields
        )

        # Step 4: 提交登录
        success = await self._submit_login(form_data)
        if success:
            self._logged_in = True
            self._cookies = dict(self._http.cookies)
            logger.info("登录成功！")
        return success

    async def _fetch_login_page(self) -> Optional[dict[str, str]]:
        """GET 登录页，提取隐藏表单域"""
        url = urljoin(self.base_url, settings.EDU_LOGIN_PATH)
        logger.info(f"获取登录页: {url}")

        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"登录页获取失败: {e}")
            return None

        hidden = self._extract_hidden_fields(resp.text)
        logger.info(f"提取到 {len(hidden)} 个隐藏字段: {list(hidden.keys())}")
        return hidden

    async def _resolve_captcha(self) -> Optional[str]:
        """获取验证码图片并识别"""
        captcha_url = urljoin(self.base_url, settings.EDU_CAPTCHA_PATH)
        logger.info(f"获取验证码: {captcha_url}")

        try:
            resp = await self._http.get(captcha_url)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"验证码获取失败: {e}")
            return None

        image_bytes = resp.content
        logger.info(f"验证码图片大小: {len(image_bytes)} bytes")

        # 预处理 + 识别
        processed = self.captcha_solver.preprocess(image_bytes)
        result = await self.captcha_solver.solve(processed)

        if result:
            # 清理非字母数字字符
            result = re.sub(r"[^a-zA-Z0-9]", "", result)
            logger.info(f"验证码识别结果: '{result}'")
        else:
            logger.warning("验证码识别返回空结果")

        return result

    async def _submit_login(self, form_data: dict[str, str]) -> bool:
        """POST 提交登录表单"""
        url = urljoin(self.base_url, settings.EDU_LOGIN_PATH)
        logger.info(f"提交登录表单: {url}")

        try:
            resp = await self._http.post(url, data=form_data)
            resp.raise_for_status()

            # 判断登录是否成功 —— 看跳转或响应中是否出现"密码错误"等关键词
            body = resp.text
            fail_keywords = ["密码错误", "验证码错误", "用户名不存在", "认证失败"]
            if any(kw in body for kw in fail_keywords):
                logger.warning("登录被拒绝（密码错误 / 验证码错误）")
                return False

            # 大部分教务系统登录成功会 302 跳转
            if resp.status_code == 200 and len(resp.history) > 0:
                logger.info(f"登录成功 (重定向链: {len(resp.history)} 次)")
                return True

            if resp.status_code == 200 and "main" in body.lower():
                return True

            # 若拿不准，通过是否能访问到需要认证的页面来判断
            return await self._verify_login()
        except Exception as e:
            logger.error(f"登录提交异常: {e}")
            return False

    async def _verify_login(self) -> bool:
        """访问一个需要登录的页面，验证 session 是否有效"""
        test_url = urljoin(self.base_url, "/student/info")  # 常见路径
        try:
            resp = await self._http.get(test_url)
            if resp.status_code == 200 and "登录" not in resp.text[:200]:
                return True
        except Exception:
            pass
        return False

    # ──────────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────────

    def _extract_hidden_fields(self, html: str) -> dict[str, str]:
        """用 BeautifulSoup 提取所有 <input type=hidden> 的 name/value"""
        fields = {}
        soup = BeautifulSoup(html, "lxml")
        for inp in soup.find_all("input", type=lambda v: v and "hidden" in v.lower()):
            name = inp.get("name")
            value = inp.get("value", "")
            if name:
                fields[name] = value

        # 兼容 ASP.NET 的 __VIEWSTATE / __EVENTVALIDATION
        for tag in soup.find_all("input", id=lambda v: v and v.startswith("__")):
            name = tag.get("name") or tag.get("id")
            value = tag.get("value", "")
            if name and name not in fields:
                fields[name] = value

        # 兼容 Spring/URP 的 _csrf / _eventId / execution
        for inp in soup.find_all("input"):
            name = inp.get("name") or ""
            if any(k in name.lower() for k in ["csrf", "execution", "eventid"]):
                value = inp.get("value", "")
                fields[name] = value

        return fields

    def _build_login_form(
        self,
        username: str,
        password: str,
        captcha: str,
        hidden: dict[str, str],
    ) -> dict[str, str]:
        """根据教务系统类型构造登录表单"""
        form = dict(hidden)  # 先包含所有隐藏字段

        if self.system_type == "zhengfang":
            form["txtUserName"] = username
            form["txtPassword"] = password
            form["txtSecretCode"] = captcha
            form["btnLogin"] = "登录"
        elif self.system_type == "qiangzhi":
            form["account"] = username
            form["pwd"] = password
            form["captcha"] = captcha
        elif self.system_type == "urp":
            form["zjh1"] = username
            form["mm1"] = password
            form["yzm"] = captcha
        else:
            # 通用: 尝试常见字段名
            form["username"] = username
            form["password"] = password
            form["captcha"] = captcha

        return form

    def _build_schedule_url(
        self,
        building: str = "",
        room: str = "",
        semester: str = "",
    ) -> str:
        """构造课表查询 URL（不同系统格式不同）"""
        if self.system_type == "zhengfang":
            url = urljoin(self.base_url, "/schedule/query")
            params = f"?building={building}&room={room}"
            if semester:
                params += f"&semester={semester}"
            return url + params
        elif self.system_type == "qiangzhi":
            return urljoin(self.base_url, f"/schedule?building={building}")
        elif self.system_type == "urp":
            return urljoin(self.base_url, f"/teaching/schedule?building={building}")
        return urljoin(self.base_url, f"/schedule?building={building}")

    @staticmethod
    def _captcha_is_mandatory() -> bool:
        """当前系统是否需要验证码（正方系统大部分需要）"""
        return settings.EDU_SYSTEM_TYPE in ("zhengfang", "urp")
