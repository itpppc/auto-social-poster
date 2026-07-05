# -*- coding: utf-8 -*-
"""
LINE AI Auto-Reply — AI ตอบลูกค้าอัตโนมัติแทนคน
- รับ webhook จาก LINE เมื่อลูกค้าพิมพ์
- ใช้ Gemini ตอบเป็นผู้ช่วยขาย
- ถ้าลูกค้าอยากคุยคน → ส่งข้อความ + ปุ่มติดต่อเจ้าหน้าที่
- เก็บ context การคุย (ต่อบทสนทนาได้)
"""
import os
import re
import json
import hmac
import base64
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

LINE_API = "https://api.line.me/v2/bot"

# เก็บ conversation context ต่อ user
_CONTEXT_FILE = Path(__file__).parent / "line_conversations.json"
_MAX_HISTORY = 8  # เก็บ 8 ข้อความล่าสุด

# คำที่บ่งบอกว่าลูกค้าต้องการคุยกับคนจริง
HUMAN_KEYWORDS = [
    "คุยกับคน", "ติดต่อเจ้าหน้าที่", "แอดมิน", "คนจริง", "พนักงาน",
    "โทรหา", "call center", "เจ้าหน้าที่", "human", "agent", "admin",
    "ขอเบอร์", "ติดต่อคน", "คุยกับแอดมิน", "พูดกับคน",
]


def _load_context() -> dict:
    if _CONTEXT_FILE.exists():
        try:
            return json.loads(_CONTEXT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_context(data: dict):
    try:
        # เก็บแค่ 100 user ล่าสุด กัน file ใหญ่
        if len(data) > 100:
            items = sorted(data.items(), key=lambda x: x[1].get("last_ts", 0), reverse=True)
            data = dict(items[:100])
        _CONTEXT_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"save context failed: {e}")


class LineAIReply:
    def __init__(self, config):
        self.config = config
        self.token = config.line_channel_access_token
        self.channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
        self.contact_phone = os.getenv("CONTACT_PHONE", "0909728573")
        self.contact_line = os.getenv("CONTACT_LINE", "@itpppc")
        self.business_info = os.getenv("BUSINESS_INFO", "")

        # Gemini client
        self._gemini = None
        if config.gemini_api_key:
            try:
                from google import genai
                self._gemini = genai.Client(api_key=config.gemini_api_key)
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

    # ─── Webhook signature verification ───
    def verify_signature(self, body: bytes, signature: str) -> bool:
        if not self.channel_secret:
            return True  # skip ถ้าไม่ได้ตั้ง secret (dev mode)
        hash_val = hmac.new(self.channel_secret.encode(), body, hashlib.sha256).digest()
        expected = base64.b64encode(hash_val).decode()
        return hmac.compare_digest(expected, signature)

    # ─── Reply API ───
    def reply(self, reply_token: str, messages: list):
        r = requests.post(
            f"{LINE_API}/message/reply",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            json={"replyToken": reply_token, "messages": messages[:5]},
            timeout=15,
        )
        if r.status_code != 200:
            logger.error(f"LINE reply failed: {r.status_code} {r.text[:200]}")
        return r.status_code == 200

    # ─── Push API (ส่งเข้าไปหา user โดยไม่ต้องมี reply token) ───
    def push(self, user_id: str, messages: list):
        r = requests.post(
            f"{LINE_API}/message/push",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            json={"to": user_id, "messages": messages[:5]},
            timeout=15,
        )
        return r.status_code == 200

    # ─── ตรวจว่าลูกค้าอยากคุยกับคน ───
    def wants_human(self, text: str) -> bool:
        t = text.lower()
        return any(kw in t for kw in HUMAN_KEYWORDS)

    # ─── AI ตอบลูกค้า ───
    def generate_reply(self, user_id: str, user_text: str) -> str:
        if not self._gemini:
            return self._fallback_reply(user_text)

        # โหลด context การคุยเดิม
        ctx = _load_context()
        history = ctx.get(user_id, {}).get("history", [])

        history_text = ""
        for h in history[-_MAX_HISTORY:]:
            role = "ลูกค้า" if h["role"] == "user" else "ผู้ช่วย"
            history_text += f"{role}: {h['text']}\n"

        prompt = f"""คุณคือผู้ช่วยขายมืออาชีพของ TON AI Tech — บริษัทโซลูชัน IT ครบวงจร
ตอบลูกค้าใน LINE แบบเป็นกันเอง สุภาพ กระชับ ช่วยปิดการขาย

ข้อมูลธุรกิจ:
- Smart Factory & OEE Dashboard (ระบบโรงงานอัจฉริยะ)
- Smart Aqua Farm IoT (ฟาร์มกุ้ง/ปลาอัจฉริยะ)
- Smart CCTV AI Detection (กล้อง AI ตรวจจับ)
- Network & Server, Cybersecurity
- Custom Software (Web/Mobile/ERP)
{self.business_info}

ติดต่อ: LINE {self.contact_line} · โทร {self.contact_phone}

กฎการตอบ:
1. ตอบสั้น กระชับ 2-4 บรรทัด (LINE ไม่ชอบข้อความยาว)
2. เป็นกันเอง มี emoji เล็กน้อย
3. ถ้าลูกค้าถามราคา → บอกว่าขึ้นกับความต้องการ ชวนให้บอกรายละเอียด/นัด demo
4. ถ้าลูกค้าสนใจ → เสนอ Demo ฟรี + ขอข้อมูลติดต่อ
5. พยายามได้ชื่อ/เบอร์/ความต้องการ เพื่อให้ทีมติดตามต่อ
6. ห้ามแต่งข้อมูลที่ไม่รู้ — ถ้าไม่แน่ใจให้เสนอติดต่อทีม

บทสนทนาก่อนหน้า:
{history_text}
ลูกค้า: {user_text}
ผู้ช่วย:"""

        MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        for model in MODELS:
            try:
                from google.genai import types
                r = self._gemini.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=500),
                )
                reply_text = r.text.strip()
                # บันทึก context
                self._update_context(user_id, user_text, reply_text)
                return reply_text
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    continue
                logger.warning(f"{model} reply failed: {e}")

        return self._fallback_reply(user_text)

    def _fallback_reply(self, user_text: str) -> str:
        """ตอบแบบ template เมื่อ AI ล่ม"""
        t = user_text.lower()
        if any(k in t for k in ["ราคา", "เท่าไหร่", "กี่บาท", "cost", "price"]):
            return (f"สอบถามราคาได้เลยครับ 😊 ราคาขึ้นอยู่กับความต้องการของแต่ละธุรกิจ\n"
                    f"รบกวนบอกรายละเอียดที่สนใจ หรือนัด Demo ฟรีได้เลยครับ\n"
                    f"📞 {self.contact_phone} · LINE {self.contact_line}")
        if any(k in t for k in ["สนใจ", "อยากได้", "ต้องการ", "demo"]):
            return (f"ขอบคุณที่สนใจครับ! 🙏 เรามี Demo ฟรีให้ดูก่อนตัดสินใจ\n"
                    f"รบกวนขอชื่อ + เบอร์ติดต่อ ทีมงานจะติดต่อกลับครับ\n"
                    f"📞 {self.contact_phone}")
        return (f"สวัสดีครับ 😊 TON AI Tech ยินดีให้บริการ\n"
                f"เรารับทำระบบ Smart Factory, IoT, CCTV AI, Software\n"
                f"สนใจเรื่องไหนสอบถามได้เลยครับ 📞 {self.contact_phone}")

    def _update_context(self, user_id: str, user_text: str, reply_text: str):
        ctx = _load_context()
        if user_id not in ctx:
            ctx[user_id] = {"history": []}
        ctx[user_id]["history"].append({"role": "user", "text": user_text})
        ctx[user_id]["history"].append({"role": "assistant", "text": reply_text})
        ctx[user_id]["history"] = ctx[user_id]["history"][-_MAX_HISTORY * 2:]
        ctx[user_id]["last_ts"] = int(time.time())
        _save_context(ctx)

    # ─── ปุ่มติดต่อเจ้าหน้าที่ (Flex/Quick Reply) ───
    def _contact_human_message(self) -> dict:
        return {
            "type": "text",
            "text": (f"รับทราบครับ 🙏 กำลังโอนสายให้เจ้าหน้าที่\n\n"
                     f"ระหว่างรอ ติดต่อตรงได้เลยครับ:\n"
                     f"📞 โทร: {self.contact_phone}\n"
                     f"💬 LINE: {self.contact_line}\n\n"
                     f"เจ้าหน้าที่จะติดต่อกลับโดยเร็วครับ"),
        }

    # ─── Main handler — ประมวลผล 1 event ───
    def handle_message_event(self, event: dict):
        """จัดการ event ข้อความจากลูกค้า"""
        if event.get("type") != "message":
            return
        msg = event.get("message", {})
        if msg.get("type") != "text":
            # ลูกค้าส่งรูป/sticker → ตอบทั่วไป
            reply_token = event.get("replyToken")
            if reply_token:
                self.reply(reply_token, [{
                    "type": "text",
                    "text": f"ขอบคุณครับ 😊 มีอะไรให้ช่วยไหมครับ?\n📞 {self.contact_phone}",
                }])
            return

        user_text = msg.get("text", "")
        user_id = event.get("source", {}).get("userId", "")
        reply_token = event.get("replyToken", "")

        if not reply_token:
            return

        logger.info(f"LINE msg from {user_id[:8]}: {user_text[:50]}")

        # ตรวจว่าอยากคุยกับคน
        if self.wants_human(user_text):
            self.reply(reply_token, [self._contact_human_message()])
            return

        # AI ตอบ
        ai_text = self.generate_reply(user_id, user_text)

        # เพิ่ม Quick Reply ปุ่ม "ติดต่อเจ้าหน้าที่" ทุกข้อความ
        messages = [{
            "type": "text",
            "text": ai_text,
            "quickReply": {
                "items": [
                    {
                        "type": "action",
                        "action": {"type": "message", "label": "📞 คุยกับเจ้าหน้าที่",
                                   "text": "ขอคุยกับเจ้าหน้าที่"},
                    },
                    {
                        "type": "action",
                        "action": {"type": "message", "label": "💰 สอบถามราคา",
                                   "text": "สอบถามราคา"},
                    },
                    {
                        "type": "action",
                        "action": {"type": "message", "label": "🎬 ดู Demo",
                                   "text": "ขอดู Demo"},
                    },
                ]
            },
        }]
        self.reply(reply_token, messages)


def handle_webhook(config, body_bytes: bytes, signature: str) -> dict:
    """Entry point — เรียกจาก Flask webhook route"""
    handler = LineAIReply(config)

    # Verify signature
    if not handler.verify_signature(body_bytes, signature):
        logger.warning("LINE webhook signature invalid")
        return {"status": "invalid_signature"}

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {"status": "bad_json"}

    for event in data.get("events", []):
        try:
            handler.handle_message_event(event)
        except Exception as e:
            logger.error(f"handle event error: {e}")

    return {"status": "ok"}
