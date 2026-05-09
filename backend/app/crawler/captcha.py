"""
验证码识别模块
支持三种策略: local (ddddocr) / openai (GPT-4o Vision) / third-party
"""
import base64
import io
from typing import Optional

import httpx
from PIL import Image
from loguru import logger

from app.config import settings


class CaptchaSolver:
    """验证码识别器"""

    def __init__(self, method: str = ""):
        self.method = method or settings.CAPTCHA_SOLVER
        self._ocr = None  # lazy init ddddocr

    def _get_local_ocr(self):
        if self._ocr is None:
            try:
                import ddddocr
                self._ocr = ddddocr.DdddOcr(show_ad=False)
            except ImportError:
                logger.warning("ddddocr 未安装，回退到 OpenAI 方案")
                self.method = "openai"
        return self._ocr

    async def solve(self, image_bytes: bytes) -> Optional[str]:
        """入口：根据配置的策略识别验证码"""
        try:
            if self.method == "local":
                return await self._solve_local(image_bytes)
            elif self.method == "openai":
                return await self._solve_openai(image_bytes)
            elif self.method == "third-party":
                return await self._solve_third_party(image_bytes)
            else:
                logger.error(f"未知验证码策略: {self.method}")
                return None
        except Exception as e:
            logger.error(f"验证码识别失败: {e}")
            return None

    async def _solve_local(self, image_bytes: bytes) -> Optional[str]:
        """本地 OCR 识别 (ddddocr)"""
        ocr = self._get_local_ocr()
        if not ocr:
            return None
        result = ocr.classification(image_bytes)
        logger.info(f"[Local OCR] 识别结果: {result}")
        return result

    async def _solve_openai(self, image_bytes: bytes) -> Optional[str]:
        """调用 GPT-4o Vision 识别验证码"""
        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_img}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.OPENAI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "请只输出图片中的验证码字符，不要输出任何其他内容:"},
                                {"type": "image_url", "image_url": {"url": data_uri}},
                            ],
                        }
                    ],
                    "max_tokens": 10,
                },
            )
            data = resp.json()
            result = data["choices"][0]["message"]["content"].strip()
            logger.info(f"[OpenAI Vision] 识别结果: {result}")
            return result

    async def _solve_third_party(self, image_bytes: bytes) -> Optional[str]:
        """接入第三方打码平台 (如 YesCaptcha / 2Captcha)"""
        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "key": settings.CAPTCHA_THIRD_PARTY_KEY,
            "method": "base64",
            "body": base64_img,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(settings.CAPTCHA_THIRD_PARTY_URL, json=payload)
            data = resp.json()
            result = data.get("result", data.get("text", ""))
            logger.info(f"[Third-Party] 识别结果: {result}")
            return result

    @staticmethod
    def preprocess(image_bytes: bytes) -> bytes:
        """对验证码图片做灰度+二值化预处理，提高识别率"""
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        threshold = 128
        img = img.point(lambda x: 255 if x > threshold else 0)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
