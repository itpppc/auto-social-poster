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

    def _fallback_prompt(self, topic: str, niche: str) -> str:
        """สร้าง prompt ตรงๆ จาก niche/topic — ไม่ต้องใช้ Gemini"""
        # Map Thai niches → English visual themes
        n = (niche or "").lower()
        if any(k in n for k in ["smart factory", "iot", "oee", "industry", "โรงงาน", "ฟาร์ม"]):
            scene = "modern smart factory floor with IoT sensors and digital OEE dashboard screens"
        elif any(k in n for k in ["cctv", "ai", "surveillance"]):
            scene = "professional control room with multiple CCTV monitor screens and AI detection overlays"
        elif any(k in n for k in ["network", "server", "cybersecurity"]):
            scene = "modern data center with server racks, network equipment, blue LED lighting"
        elif any(k in n for k in ["social media", "marketing", "facebook ads"]):
            scene = "social media marketing dashboard on laptop screen with analytics graphs going up"
        elif any(k in n for k in ["อาหาร", "ทะเล", "ขนมจีน", "สลัด", "ออร์แกนิค"]):
            scene = "premium Thai food photography, delicious freshly prepared dish on rustic wooden table"
        elif any(k in n for k in ["ไอที", "คอมพิวเตอร์", "โน๊ตบุ๊ค"]):
            scene = "professional workspace with modern laptops, IT equipment, clean tech aesthetic"
        else:
            scene = f"professional business scene related to {niche[:60]}"

        return (f"{scene}, photorealistic commercial photography, "
                f"vibrant lighting, blue and orange accent colors, "
                f"shallow depth of field, 16:9 composition, high quality, no text, no logos")

    def generate_prompt(self, topic: str, niche: str, content_summary: str = "") -> str:
        """พยายามให้ Gemini ทำ prompt ก่อน — fallback ถ้า quota หมด"""
        from google.genai import types

        meta = f"""Create a SHORT (max 50 words) English image generation prompt for a marketing post.
Topic: {topic}
Business: {niche}

Style: photorealistic commercial photo, real business scenario (factory/IoT/dashboard/office), vibrant lighting, blue/orange/cyan accents, 16:9, NO text, NO logos.

Reply with the prompt ONLY."""

        MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        for model in MODELS:
            try:
                r = self._gemini().models.generate_content(
                    model=model, contents=meta,
                    config=types.GenerateContentConfig(temperature=0.6, max_output_tokens=150),
                )
                prompt = r.text.strip().strip('"').strip("'")
                logger.info(f"Image prompt ({model}): {prompt[:80]}")
                return prompt
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
                    logger.info(f"Gemini quota exceeded → use fallback prompt")
                    break  # ข้าม model อื่นเลย เพราะทุก model share quota
                elif "503" in err:
                    continue  # ลอง model ถัดไป
                else:
                    break

        fallback = self._fallback_prompt(topic, niche)
        logger.info(f"Fallback prompt: {fallback[:80]}")
        return fallback

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
