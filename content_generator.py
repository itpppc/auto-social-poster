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

        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite",   # 1,500 req/วัน free (เทียบกับ 2.5 = 20)
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.85,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        return self._parse_response(response.text, idea)

    def _build_prompt(self, idea: TopicIdea, niche: Optional[str] = None) -> str:
        active_niche = niche or self.config.content_niche
        keyword_hint = ""
        if idea.keywords:
            keyword_hint = f"\nคำสำคัญที่ควรกล่าวถึง: {', '.join(idea.keywords)}"

        return f"""คุณคือ content creator มืออาชีพระดับล้านวิว เชี่ยวชาญด้าน "{active_niche}"
ภารกิจ: สร้าง content ที่ดึงให้คนกดติดตาม Page/แชนแนล (เพราะ Page นี้เพิ่งเปิด ต้องการคนติดตามใหม่)
สไตล์: เป็นมิตร เข้าใจง่าย ขำได้ มีประโยชน์จริง สร้างความเชี่ยวชาญ (authority) ในเรื่องนี้

หัวข้อวันนี้: "{idea.title}"{keyword_hint}

โครงสร้าง content ที่ดึงคนติดตาม:
1. Hook 2 บรรทัดแรก → ทำให้คนหยุดเลื่อน (ตกใจ/ขำ/relatable/curiosity gap)
2. Value → ให้ความรู้/เคล็ดลับจริงเกี่ยวกับ {active_niche} ที่คนอ่านได้ประโยชน์
3. Social proof / authority → ใส่ตัวเลข สถิติ หรือเรื่องราวที่ดูน่าเชื่อถือ
4. CTA → กระตุ้นให้กด follow, comment, share, tag เพื่อน

เขียน content ให้เหมาะกับแต่ละ platform ตอบเป็น JSON เท่านั้น:
{{
  "facebook_post": "โพสต์ Facebook 180-280 คำ — Hook แรง 2 บรรทัด · ให้ประโยชน์จริง 2-3 จุด · มี emoji เยอะ · จบด้วยคำถาม + เชิญกดติดตาม Page เพื่อรับคอนเทนต์แบบนี้ทุกวัน",
  "line_message": "ข้อความ LINE 80-120 คำ — สั้น กระชับ มี value · bullet point • · emoji 4-6 ตัว · จบด้วย CTA ชวนติดตามหรือทักแชท",
  "tiktok_script": "Caption TikTok 60-100 คำ — Hook ใน 5 วินาทีแรก · เนื้อหากระตุ้นให้ดูจบ · จบด้วย 'follow เพื่อดูคอนเทนต์ {active_niche} ทุกวัน' + hashtag",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5", "#hashtag6", "#hashtag7", "#hashtag8"],
  "call_to_action": "CTA 1 ประโยค สั้น ทรงพลัง — ชวน follow/share/tag เพื่อน"
}}

กฎ:
- ภาษาไทยธรรมชาติ เหมือนคนคุยกัน ไม่เป็นทางการเกินไป
- เนื้อหาต้องเชื่อมโยงกับ "{active_niche}" ทุกครั้ง — แม้หัวข้อจะดูไม่เกี่ยว ก็หามุมเชื่อมให้ได้
- ใช้ emoji อย่างน้อย 5 ตัวต่อ post
- Hashtags ผสมไทย-อังกฤษ เกี่ยวกับ {active_niche} โดยตรง 5 ตัว + trending/generic 3 ตัว
- ห้ามเนื้อหาหยาบคาย เหยียด โฆษณาเกินจริง หรือทำให้คนรู้สึกถูกขาย"""

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
