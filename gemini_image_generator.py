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

    def _fallback_prompt(self, topic: str, niche: str, content_summary: str = "") -> str:
        """สร้าง prompt ตรงเนื้อหา — รวม topic + niche + content keywords"""
        # ดึง keyword จาก topic/content
        text = f"{topic} {niche} {content_summary}".lower()

        # หาว่าเนื้อหาเกี่ยวกับอะไรเป็นหลัก
        themes = []
        keyword_map = [
            (["smart factory","oee","downtime","โรงงาน","สายการผลิต","plc","scada"],
             "modern smart factory production line with real-time OEE dashboard monitors, robotic arms, industrial IoT sensors, blue LED indicator lights"),
            (["aqua","ฟาร์มกุ้ง","ฟาร์มปลา","do","ph","แอมโมเนีย","น้ำ"],
             "shrimp/fish farm pond with IoT water quality sensors floating, beautiful sunset lighting over aquaculture facility"),
            (["cctv","กล้อง","สำรวจ","ai detection","ตรวจจับ","surveillance"],
             "modern security control room with wall of CCTV monitors showing AI-detected people and vehicles with overlay boxes"),
            (["network","เครือข่าย","server","เซิร์ฟเวอร์","firewall","lan"],
             "modern enterprise data center with neat server racks, blue LED status lights, fiber optic cables"),
            (["cybersecurity","ปลอดภัย","ไซเบอร์","pentest","siem","zero trust"],
             "cybersecurity operations center, multiple monitors showing security dashboards, abstract digital lock graphics"),
            (["social media","facebook ads","tiktok","instagram","การตลาด","marketing"],
             "modern marketing workspace with laptop showing social media analytics dashboard with growing engagement graphs, smartphone displaying ads"),
            (["custom software","erp","mes","mobile app","web app","ซอฟต์แวร์"],
             "developer workspace with multiple monitors displaying clean code, modern UI mockups, professional tech office"),
            (["ขนมจีน","น้ำยา","อาหารใต้","อาหารทะเล","seafood"],
             "premium Thai southern food photography, beautiful bowl of Khanom Jeen with curry sauce, fresh seafood on rustic wooden table, top down shot"),
            (["สลัด","ผักออร์แกนิค","คลีน","ไฮโดรโปนิค","organic"],
             "vibrant fresh salad bowl photography, colorful organic vegetables, hydroponic greens, healthy meal styling on wooden table"),
            (["คอมพิวเตอร์มือสอง","โน๊ตบุ๊ค","ไอที","laptop","คอมพ์"],
             "modern professional laptop on clean desk with smartphone and tech accessories, soft natural lighting"),
            (["ai","artificial intelligence","ปัญญาประดิษฐ์","gpt","gemini"],
             "futuristic AI concept visualization, abstract neural network connections, glowing blue circuit patterns on dark background"),
            (["dashboard","แสดงผล","สถิติ","กราฟ"],
             "modern business intelligence dashboard on large screen, beautiful data visualization with charts and KPIs"),
        ]

        for keywords, scene in keyword_map:
            if any(k in text for k in keywords):
                themes.append(scene)

        # ถ้าเจอหลายธีม รวม 2 อันแรก
        if themes:
            scene = themes[0] if len(themes) == 1 else f"{themes[0]}, with elements of {themes[1].split(',')[0]}"
        else:
            # generic professional business
            niche_clean = (niche or "business")[:80]
            scene = f"professional commercial photo representing {niche_clean}, modern stylish composition"

        return (f"{scene}, photorealistic commercial photography, "
                f"cinematic lighting, vibrant blue and orange accents, "
                f"shallow depth of field, ultra detailed, 16:9 composition, "
                f"no text, no watermarks, no logos, advertising quality")

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

        fallback = self._fallback_prompt(topic, niche, content_summary)
        logger.info(f"Fallback prompt: {fallback[:100]}")
        return fallback

    # Quality boosters แยกตามประเภทรูป
    QUALITY_BOOSTERS = {
        "photo": ("photorealistic commercial advertising photography, "
                  "shot on Hasselblad H6D 85mm f/1.8, golden hour lighting, "
                  "cinematic depth of field, ultra detailed textures, "
                  "professional color grading, premium magazine quality, "
                  "award-winning composition, hyper-realistic, 8K UHD, "
                  "vibrant colors, soft bokeh, sharp focus"),
        "illustration": ("modern premium vector illustration, SaaS aesthetic, "
                         "vibrant gradient palette, clean lines, polished infographic, "
                         "3D render with soft shadows, ultra detailed, "
                         "trending on Behance and Dribbble, brand-quality design"),
        "lifestyle": ("lifestyle commercial photography, candid authentic moment, "
                      "natural soft window lighting, warm cinematic color grading, "
                      "shallow depth of field, premium brand campaign aesthetic, "
                      "magazine quality, professional retouching"),
        "product": ("luxury product photography, studio lighting setup, "
                    "clean minimal background, hero shot composition, "
                    "ultra sharp focus, professional retouching, "
                    "high-end commercial advertising, 8K UHD"),
    }

    NEGATIVE = ("blurry, low quality, distorted, deformed, watermark, text, logo, "
                "signature, low resolution, jpeg artifacts, oversaturated, "
                "amateur, bad anatomy, dull colors, ugly")

    def _detect_style(self, prompt: str) -> str:
        p = prompt.lower()
        if any(k in p for k in ["illustration", "vector", "3d render", "isometric", "flat", "infographic", "cartoon"]):
            return "illustration"
        if any(k in p for k in ["product", "studio", "luxury", "hero shot", "packshot"]):
            return "product"
        if any(k in p for k in ["family", "people", "enjoying", "candid", "lifestyle", "person"]):
            return "lifestyle"
        return "photo"

    def generate_image(self, prompt: str, output_path: Optional[str] = None,
                       width: int = 1920, height: int = 1080,
                       model: str = "flux") -> Optional[str]:
        """Render รูปจาก prompt ผ่าน Pollinations.ai (ฟรี ไม่ต้อง key)
        model: flux | flux-realism | flux-anime | flux-3d | turbo
        """
        style = self._detect_style(prompt)
        booster = self.QUALITY_BOOSTERS[style]
        full_prompt = f"{prompt}, {booster}"

        seed = int(time.time()) % 100000
        url = (POLLINATIONS_BASE + quote(full_prompt)
               + f"?width={width}&height={height}&seed={seed}"
               + f"&nologo=true&enhance=true&nofeed=true&model={model}"
               + f"&negative_prompt={quote(self.NEGATIVE)}")

        try:
            logger.info(f"Rendering [{style}/{model}] {width}x{height} via Pollinations...")
            r = requests.get(url, timeout=120)
            if r.status_code != 200 or len(r.content) < 5000:
                logger.warning(f"Pollinations status={r.status_code}, len={len(r.content)}")
                # Try turbo as fallback
                if model == "flux":
                    return self.generate_image(prompt, output_path, width, height, model="turbo")
                return None

            from PIL import Image, ImageEnhance
            img = Image.open(io.BytesIO(r.content))
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Post-process — เพิ่มความพรีเมียม
            img = ImageEnhance.Contrast(img).enhance(1.08)
            img = ImageEnhance.Color(img).enhance(1.12)
            img = ImageEnhance.Sharpness(img).enhance(1.15)

            if not output_path:
                output_path = str(Path(tempfile.gettempdir()) / f"ai_img_{int(time.time()*1000)}.jpg")
            img.save(output_path, "JPEG", quality=92, optimize=True)
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
