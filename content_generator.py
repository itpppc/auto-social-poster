"""
AI Content Generator using Google Gemini API (FREE)
- ฟรี 1,500 requests/วัน, 15 requests/นาที
- สมัครได้ที่: https://aistudio.google.com/

Content ideas มาจาก (เรียงลำดับ):
  1. ปฏิทินไทย      — เทศกาล/วันสำคัญวันนี้
  2. Google Trends   — กำลังฮิตในไทยตอนนี้
  3. RSS ข่าวไทย     — หัวข้อข่าวล่าสุด
  4. Evergreen       — หัวข้อคลาสสิค (fallback)
"""
from google import genai
from google.genai import types
import json
import logging
from dataclasses import dataclass
from typing import Optional

from config import Config
from content_sources import ContentSources, TopicIdea

logger = logging.getLogger(__name__)


@dataclass
class GeneratedContent:
    topic: str
    source: str           # ที่มาของ topic idea
    facebook_post: str
    line_message: str
    tiktok_script: str
    hashtags: list[str]
    call_to_action: str


class ContentGenerator:
    def __init__(self, config: Config):
        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)
        self.sources = ContentSources(niche=config.content_niche)

    def generate(self, custom_topic: Optional[str] = None, niche: Optional[str] = None) -> GeneratedContent:
        active_niche = niche or self.config.content_niche
        if custom_topic:
            idea = TopicIdea(title=custom_topic, source="Manual", keywords=[])
        else:
            sources = ContentSources(niche=active_niche) if niche else self.sources
            idea = sources.get_best_topic()

        logger.info(f"Topic source: {idea.source} | {idea.title} | niche: {active_niche}")
        prompt = self._build_prompt(idea, active_niche)

        # ลอง 3 models ตามลำดับ + retry
        import time as _time
        MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        last_error = None
        for model in MODELS:
            for attempt in range(3):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.85,
                            max_output_tokens=4096,
                            response_mime_type="application/json",
                        ),
                    )
                    logger.info(f"Generated with {model} (attempt {attempt+1})")
                    return self._parse_response(response.text, idea)
                except Exception as e:
                    last_error = e
                    code = str(e)
                    if "503" in code or "UNAVAILABLE" in code or "429" in code:
                        wait = 2 ** attempt
                        logger.warning(f"{model} busy, retry in {wait}s")
                        _time.sleep(wait)
                    else:
                        break  # error อื่นๆ ไม่ต้อง retry model นี้
            logger.warning(f"{model} failed all retries, trying next model")
        raise last_error or Exception("All models failed")

    def _build_prompt(self, idea: TopicIdea, niche: Optional[str] = None) -> str:
        active_niche = niche or self.config.content_niche
        keyword_hint = ""
        if idea.keywords:
            keyword_hint = f"\nคำสำคัญที่ควรกล่าวถึง: {', '.join(idea.keywords)}"

        return f"""คุณคือ Direct-Response Copywriter ระดับโลก เชี่ยวชาญด้าน "{active_niche}"
ภารกิจ: เขียน content ขายของ/ปิดดีล/ดึงคนทักไลน์ปรึกษาทันที — ไม่ใช่แค่ engagement สวยๆ

ติดต่อ: LINE @itpppc · โทร 0909728573 · เว็บ ton-ai-tech.web.app

หัวข้อวันนี้: "{idea.title}"{keyword_hint}

═══ สูตร AIDA สำหรับยอดขาย ═══
A (Attention): Hook ที่ "เจาะใจ pain point" หรือ "ตกใจกับตัวเลข"
   ❌ "วันนี้มาคุยเรื่อง..." (อ่อนเกินไป)
   ✅ "ผู้ประกอบการเสียเงินเดือนละ 50,000฿ เพราะระบบนี้ไม่มี"
   ✅ "ฟาร์มกุ้ง 1 บ่อขาดทุน 2 แสนเพราะรู้ช้าไป 3 ชม."

I (Interest): ระบุ pain point จริงของลูกค้า + ผลที่ตามมา (loss aversion)
   • ใส่ "ปัญหาที่เจอบ่อย" 2-3 อย่าง
   • พูดถึงผลกระทบเป็นตัวเลข (เงิน/เวลา/โอกาส)

D (Desire): นำเสนอ solution พร้อมประโยชน์เป็นรูปธรรม
   • ใส่ตัวเลขชัด เช่น "ลด downtime 70%" "เพิ่ม OEE 25%"
   • Case study สั้นๆ "ลูกค้า A ทำแล้ว..."
   • Authority signals "มีประสบการณ์ X ปี" "ติดตั้งมาแล้ว Y โครงการ"
   • Risk reversal: "Demo ฟรี ดูจริงก่อนตัดสินใจ"

A (Action): CTA ทรงพลัง กระตุ้นให้ทักไลน์ทันที
   ✅ "📩 ทักไลน์ @itpppc — ปรึกษาฟรี ไม่เสียเงิน"
   ✅ "📞 โทร 0909728573 ขอใบเสนอราคา"
   ✅ "💬 Inbox มาเลย ส่ง demo ให้ดูทันที"

═══ Output: JSON เท่านั้น ═══
{{
  "facebook_post": "โพสต์ Facebook 250-400 คำ ขายของแบบ AIDA: Hook pain point/ตัวเลข + ปัญหา + solution พร้อม benefit เป็นตัวเลข + case study สั้น + CTA ทักไลน์ ใส่ emoji 8-12 ตัว ใช้ bullet • • • และเว้นบรรทัดอ่านง่าย จบด้วย contact ครบ (LINE/โทร/เว็บ)",
  "line_message": "ข้อความ LINE 120-180 คำ Direct + กระชับ: Hook 1 บรรทัด → ปัญหา 1 บรรทัด → solution พร้อม benefit ตัวเลข 2-3 จุด → CTA ทักกลับขอ demo/ราคา · emoji 5-7 ตัว",
  "tiktok_script": "Caption TikTok 80-120 คำ: Hook 5 วิแรก (ตัวเลข/pain) → 3 จุดที่ทำให้ลูกค้าได้ประโยชน์ (พร้อมตัวเลข) → CTA ทักไลน์ @itpppc + hashtag",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5", "#hashtag6", "#hashtag7", "#hashtag8"],
  "call_to_action": "CTA 1 ประโยค ขอให้ทักไลน์/โทร เน้นจุดเด่น (ฟรี/ทันที/จริง)"
}}

═══ กฎเข้ม ═══
1. ทุกโพสต์ "ต้อง" มีตัวเลข — ผลประโยชน์/ปัญหา/สถิติ (%, ฿, ชั่วโมง, จำนวน)
2. ทุกโพสต์ "ต้อง" มี contact ครบ: LINE @itpppc + โทร 0909728573 (ใน facebook_post)
3. ทุกโพสต์ "ต้อง" จบด้วย CTA ที่บังคับ action (ทักไลน์/โทร/สั่ง demo)
4. ใส่ "Risk reversal" — "Demo ฟรี" / "ปรึกษาฟรี" / "ดูจริงก่อนตัดสินใจ"
5. ภาษาไทยธรรมชาติแบบเจ้าของกิจการคุย — มั่นใจ ตรง ไม่อ้อมค้อม
6. หัวข้อต้องเชื่อมกับ "{active_niche}" — หา angle ที่ขายของให้ได้
7. ห้าม: ขายเกินจริง · clickbait · เคลมที่พิสูจน์ไม่ได้
8. Hashtags: 5 ตัวตรงสินค้า/บริการ + 3 ตัว trending/local (เช่น #กรุงเทพ #ผู้ประกอบการไทย)"""

    def get_image_query(self, topic: str, niche: str) -> str:
        """สร้าง English search query สำหรับค้นหารูปภาพ"""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=f"Write a 3-5 word English stock photo search query for this topic: '{topic}' in the niche '{niche}'. Reply with the search query ONLY, no punctuation.",
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=30,
                ),
            )
            return response.text.strip().strip("\"'")
        except Exception:
            return niche

    def _parse_response(self, response_text: str, idea: TopicIdea) -> GeneratedContent:
        import re as _re

        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        start = text.find("{")
        end = text.rfind("}") + 1
        json_str = text[start:end]

        data = self._robust_json_parse(json_str, idea)

        return GeneratedContent(
            topic=idea.title,
            source=idea.source,
            facebook_post=data.get("facebook_post", ""),
            line_message=data.get("line_message", ""),
            tiktok_script=data.get("tiktok_script", ""),
            hashtags=data.get("hashtags", []),
            call_to_action=data.get("call_to_action", ""),
        )

    def _robust_json_parse(self, json_str: str, idea: "TopicIdea") -> dict:
        """ลอง parse JSON หลายวิธี ถ้าทุกวิธีล้มเหลว ดึง field ด้วย regex"""
        import re as _re

        # Strategy 1: parse ตรงๆ
        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            pass

        # Strategy 2: ลบ control characters
        cleaned = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
        try:
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            pass

        # Strategy 3: escape quote ใน string ที่อาจไม่ได้ escape
        # หา pattern: "key": "value with "embedded" quotes",
        try:
            fixed = _re.sub(
                r'(:\s*")((?:[^"\\]|\\.)*)((?<!\\)")(?=[^,}\]]*[,}\]])',
                lambda m: m.group(1) + m.group(2).replace('"', r'\"') + m.group(3),
                cleaned,
            )
            return json.loads(fixed, strict=False)
        except json.JSONDecodeError:
            pass

        # Strategy 4 (last resort): ดึงแต่ละ field ด้วย regex
        logger.warning(f"JSON parse fully failed, extracting fields with regex")
        result = {}
        for key in ("facebook_post", "line_message", "tiktok_script", "call_to_action"):
            m = _re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, _re.DOTALL)
            if m:
                result[key] = m.group(1).encode().decode('unicode_escape', errors='replace')
        # hashtags
        m = _re.search(r'"hashtags"\s*:\s*\[(.*?)\]', cleaned, _re.DOTALL)
        if m:
            tags = _re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
            result["hashtags"] = tags
        return result
