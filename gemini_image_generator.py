# -*- coding: utf-8 -*-
"""
AI Image Generator — สร้างรูปจาก content ที่เหมาะกับ business
Pipeline: Gemini (smart prompt) → Pollinations.ai (render) → ไฟล์ JPG

ทำไมใช้ Pollinations:
- ฟรี 100% ไม่ต้อง key
- ไม่มี rate limit แบบ Gemini
- Render เร็ว 5-15 วินาที
- คุณภาพดี (รองรับ flux, sdxl)
"""
import io
import logging
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"


class GeminiImageGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _gemini(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_prompt(self, topic: str, niche: str, content_summary: str = "") -> str:
        """ให้ Gemini ออกแบบ prompt รูปสำหรับ business นี้"""
        from google.genai import types

        meta = f"""You are an expert ad designer.
Create a SHORT (max 60 words) English image generation prompt for a Facebook/LINE marketing post.

Topic: {topic}
Business: {niche}
{f"Content gist: {content_summary[:150]}" if content_summary else ""}

Image style requirements:
- Photorealistic professional commercial photography
- Real business scenarios (factory floor, IoT dashboards, smart office, control rooms)
- Vibrant lighting, blue/orange/cyan accent colors
- 16:9 ratio composition
- NO text, NO logos, NO watermarks, NO people facing camera

Reply with ONLY the prompt (no quotes, no explanation)."""

        MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        for model in MODELS:
            for attempt in range(2):
                try:
                    r = self._gemini().models.generate_content(
                        model=model, contents=meta,
                        config=types.GenerateContentConfig(temperature=0.6, max_output_tokens=200),
                    )
                    prompt = r.text.strip().strip('"').strip("'")
                    logger.info(f"Image prompt ({model}): {prompt[:100]}...")
                    return prompt
                except Exception as e:
                    if "503" in str(e) or "429" in str(e):
                        time.sleep(1 + attempt)
                    else:
                        break

        # Fallback prompt
        return (f"Professional commercial photo of {niche}, modern industrial scene, "
                f"vibrant blue and orange accents, photorealistic, high quality")

    def generate_image(self, prompt: str, output_path: Optional[str] = None,
                       width: int = 1280, height: int = 720) -> Optional[str]:
        """Render รูปจาก prompt ผ่าน Pollinations.ai (ฟรี ไม่ต้อง key)"""
        # Add quality modifiers
        full_prompt = f"{prompt}, professional photography, cinematic lighting, sharp focus, 8k, commercial advertisement"

        seed = int(time.time()) % 100000
        url = (POLLINATIONS_BASE + quote(full_prompt)
               + f"?width={width}&height={height}&seed={seed}&nologo=true&model=flux")

        try:
            logger.info(f"Rendering via Pollinations.ai...")
            r = requests.get(url, timeout=120)
            if r.status_code != 200 or len(r.content) < 5000:
                logger.warning(f"Pollinations status={r.status_code}, len={len(r.content)}")
                return None

            from PIL import Image
            img = Image.open(io.BytesIO(r.content))
            if img.mode != "RGB":
                img = img.convert("RGB")

            if not output_path:
                output_path = str(Path(tempfile.gettempdir()) / f"ai_img_{int(time.time()*1000)}.jpg")
            img.save(output_path, "JPEG", quality=88)
            logger.info(f"Image saved: {output_path} ({Path(output_path).stat().st_size//1024} KB)")
            return output_path
        except Exception as e:
            logger.error(f"Pollinations failed: {e}")
            return None

    def generate_for_post(self, topic: str, niche: str,
                          content_summary: str = "",
                          width: int = 1280, height: int = 720) -> Optional[str]:
        """Pipeline: topic → smart prompt → image"""
        prompt = self.generate_prompt(topic, niche, content_summary)
        return self.generate_image(prompt, width=width, height=height)
