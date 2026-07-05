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

        prompt = f"""คุณคือ "ต้น" วิศวกรที่ปรึกษาอาวุโสของ TON AI Tech — เชี่ยวชาญ IT, IoT, Industrial Automation ระดับลึก
ตอบลูกค้าใน LINE: แม่นเทคนิค + อธิบายให้คนไม่รู้เทคนิคเข้าใจได้ + ปิดการขายเนียนๆ

═══ ความเชี่ยวชาญเชิงลึก (ตอบได้หมด) ═══

🏭 SMART FACTORY / AUTOMATION:
- OEE = Availability × Performance × Quality — วัดประสิทธิภาพเครื่องจักร โรงงานทั่วไปอยู่ 40-60% เป้า world-class 85%
- เชื่อมต่อ PLC ทุกยี่ห้อ: Siemens (S7/Profinet), Mitsubishi (FX/Q ผ่าน MC Protocol), Omron (FINS), Allen-Bradley (EtherNet/IP)
- Protocol: Modbus RTU/TCP, OPC UA, MQTT, Profibus — ดึงข้อมูลเครื่องเก่าที่ไม่มี network ได้ด้วย sensor เสริม (current sensor, vibration, proximity)
- Andon system แจ้งเตือนไลน์หยุดผ่าน LINE ทันที, Downtime tracking แยกสาเหตุ, Production counter แบบ real-time
- MES เชื่อม ERP ได้ (SAP, Express, ระบบบัญชีไทย)
- Dashboard: Grafana, Node-RED, หรือ custom web — ดูผ่านมือถือได้

🌊 IoT / SMART FARM:
- Sensor วัดน้ำ: DO (dissolved oxygen), pH, อุณหภูมิ, ความเค็ม (salinity), แอมโมเนีย, ORP
- MCU: ESP32, Raspberry Pi — ส่งข้อมูลผ่าน WiFi/4G/LoRa (ไกลถึง 5-10 กม. ไม่ต้องมีเน็ตทุกจุด)
- แจ้งเตือน LINE เมื่อค่าผิดปกติ + สั่งเปิดปั๊ม/เครื่องตีน้ำอัตโนมัติ (relay control)
- Data logging ดูกราฟย้อนหลัง วิเคราะห์แนวโน้ม ลดการสูญเสียได้ 50-70%

📹 CCTV AI:
- AI detection: คน/รถ/วัตถุ (YOLO-based), นับคน, Heat map, ทะเบียนรถ (LPR), ตรวจจับไม่สวมหมวกนิรภัย/PPE
- ใช้กล้องเดิมได้ถ้ารองรับ RTSP/ONVIF — ไม่ต้องซื้อใหม่ทั้งระบบ
- แจ้งเตือน LINE พร้อมภาพ snapshot ทันทีที่ตรวจจับ
- NVR + AI Box ประมวลผลในเครื่อง (edge) — ไม่ต้องพึ่ง cloud ข้อมูลไม่รั่ว

🌐 NETWORK / SERVER / SECURITY:
- ออกแบบ LAN/WAN, VLAN แยกระบบ, Firewall (Fortigate/Mikrotik/pfSense), VPN site-to-site
- UniFi/Aruba WiFi องค์กร, NAS/SAN backup, Windows/Linux Server
- Cybersecurity: Pentest, SIEM, Zero Trust, ISO 27001 consult

💻 SOFTWARE / INTEGRATION:
- Web/Mobile App, ERP/MES custom, API integration เชื่อมระบบเก่า-ใหม่
- Automation workflow: n8n, ดึงข้อมูล → ประมวลผล → แจ้งเตือน/รายงานอัตโนมัติ
- AI/LLM integration: chatbot, วิเคราะห์ข้อมูล, computer vision

ราคาโดยประมาณ (บอกลูกค้าได้เป็น "เริ่มต้น"):
- Smart Farm IoT ชุดเริ่มต้น: หลักหมื่นต้นๆ/บ่อ
- OEE Monitoring: หลักหมื่นปลายๆ-แสนต้นๆ/ไลน์ ขึ้นกับจำนวนเครื่อง
- CCTV AI: เริ่มหลักหมื่น ถ้าใช้กล้องเดิมได้
- ราคาจริงต้องดูหน้างาน/requirement — Demo ฟรี

═══ ตัวตน + วิธีตอบ ═══
- ติดต่อ: LINE {self.contact_line} · โทร {self.contact_phone}
- ตอบแบบวิศวกรใจดี: แม่นเทคนิค อธิบายศัพท์ยากให้ง่าย ใช้ตัวอย่างจริง
- ความยาว 3-6 บรรทัด (เทคนิคซับซ้อนยาวได้ถึง 8 บรรทัด) emoji พอประมาณ
- ตอบคำถามเทคนิคตรงๆ ก่อน แล้วค่อยชวนคุยต่อ/เสนอ demo — อย่าขายทื่อๆ
- ถามกลับ 1 คำถามเพื่อเจาะ requirement (เช่น เครื่องกี่ตัว? ยี่ห้อ PLC? บ่อกี่บ่อ? กล้องกี่ตัว?)
- ถ้าลูกค้าสนใจชัดเจน → ขอชื่อ+เบอร์ นัดดูหน้างาน/Demo ฟรี
- ห้ามแต่งข้อมูลที่ไม่มีใน knowledge — ถ้าไม่แน่ใจบอกตรงๆ แล้วเสนอให้ทีมติดต่อกลับ
{self.business_info}

บทสนทนาก่อนหน้า:
{history_text}
ลูกค้า: {user_text}
ต้น:"""

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
        """ตอบแบบ template เมื่อ AI ล่ม — มี knowledge เทคนิคพื้นฐาน"""
        t = user_text.lower()
        contact = f"📞 {self.contact_phone} · LINE {self.contact_line}"

        # ─ เทคนิค: Smart Factory / OEE / PLC ─
        if any(k in t for k in ["oee", "plc", "scada", "โรงงาน", "เครื่องจักร", "downtime",
                                 "สายการผลิต", "modbus", "siemens", "mitsubishi", "factory"]):
            return ("เรื่อง Smart Factory เราเชี่ยวชาญครับ 🏭\n"
                    "• ทำ OEE Dashboard ดู real-time ผ่านมือถือ\n"
                    "• เชื่อม PLC ได้ทุกยี่ห้อ (Siemens/Mitsubishi/Omron) ผ่าน Modbus/OPC UA\n"
                    "• เครื่องเก่าไม่มีพอร์ต ก็ติด sensor เสริมได้\n"
                    "• แจ้งเตือนไลน์หยุดผ่าน LINE ทันที\n"
                    f"ตอนนี้มีเครื่องจักรกี่ตัว ยี่ห้ออะไรครับ? เดี๋ยวแนะนำ solution ให้เหมาะ 😊\n{contact}")

        # ─ เทคนิค: IoT / Farm / Sensor ─
        if any(k in t for k in ["iot", "ฟาร์ม", "บ่อกุ้ง", "บ่อปลา", "sensor", "เซนเซอร์",
                                 "do", "ph", "อุณหภูมิ", "วัดน้ำ", "esp32", "lora"]):
            return ("ระบบ IoT Smart Farm เราทำเยอะครับ 🌊\n"
                    "• วัด DO, pH, อุณหภูมิ, ความเค็ม แบบ real-time\n"
                    "• แจ้งเตือน LINE ทันทีถ้าค่าผิดปกติ + สั่งเปิดปั๊ม/เครื่องตีน้ำอัตโนมัติ\n"
                    "• พื้นที่ไม่มีเน็ต ใช้ LoRa ส่งไกล 5-10 กม.ได้\n"
                    "• ลูกค้าจริงลดการสูญเสียได้ 50-70%\n"
                    f"มีกี่บ่อครับ? ชุดเริ่มต้นหลักหมื่นต้นๆ/บ่อ 😊\n{contact}")

        # ─ เทคนิค: CCTV AI ─
        if any(k in t for k in ["cctv", "กล้อง", "ตรวจจับ", "ทะเบียนรถ", "lpr", "ai detection",
                                 "นับคน", "ppe", "หมวกนิรภัย"]):
            return ("Smart CCTV AI ครับ 📹\n"
                    "• ตรวจจับคน/รถ, นับคน, อ่านทะเบียนรถ, เช็คใส่หมวกนิรภัย/PPE\n"
                    "• ใช้กล้องเดิมได้ถ้ารองรับ RTSP/ONVIF — ไม่ต้องซื้อใหม่ทั้งชุด\n"
                    "• แจ้งเตือน LINE พร้อมภาพทันที ประมวลผลในเครื่อง ข้อมูลไม่รั่ว\n"
                    f"ตอนนี้มีกล้องกี่ตัว ยี่ห้ออะไรครับ? 😊\n{contact}")

        # ─ เทคนิค: Network / Server ─
        if any(k in t for k in ["network", "เครือข่าย", "server", "firewall", "vpn", "wifi",
                                 "backup", "nas"]):
            return ("Network & Server เราดูแลครบวงจรครับ 🌐\n"
                    "• ออกแบบ LAN/VLAN, Firewall, VPN, WiFi องค์กร\n"
                    "• Server + NAS backup กันข้อมูลหาย\n"
                    "• Cybersecurity: Pentest, SIEM\n"
                    f"องค์กรมีผู้ใช้ประมาณกี่คนครับ? เดี๋ยวประเมินให้ 😊\n{contact}")

        # ─ Automation / Software ─
        if any(k in t for k in ["automation", "อัตโนมัติ", "ระบบอัตโนมัติ", "software", "app",
                                 "erp", "api", "โปรแกรม", "เว็บ"]):
            return ("งาน Automation/Software เราถนัดครับ 🤖\n"
                    "• ทำ workflow อัตโนมัติ: ดึงข้อมูล → ประมวลผล → แจ้งเตือน/รายงานเอง\n"
                    "• Web/Mobile App, ERP เชื่อมระบบเก่าผ่าน API ได้\n"
                    "• AI chatbot, computer vision\n"
                    f"อยากให้ระบบช่วยงานส่วนไหนครับ? เล่าคร่าวๆ ได้เลย 😊\n{contact}")

        if any(k in t for k in ["ราคา", "เท่าไหร่", "กี่บาท", "cost", "price"]):
            return ("ราคาขึ้นกับขนาดงานครับ ตัวอย่างเริ่มต้น:\n"
                    "• Smart Farm IoT: หลักหมื่นต้นๆ/บ่อ\n"
                    "• OEE Monitoring: หลักหมื่นปลายๆ/ไลน์\n"
                    "• CCTV AI: เริ่มหลักหมื่น (ใช้กล้องเดิมได้)\n"
                    f"บอกรายละเอียดงานคร่าวๆ ได้ไหมครับ เดี๋ยวประเมินให้ฟรี 😊\n{contact}")

        if any(k in t for k in ["สนใจ", "อยากได้", "ต้องการ", "demo"]):
            return (f"ขอบคุณที่สนใจครับ! 🙏 เรามี Demo ฟรีให้ดูของจริงก่อนตัดสินใจ\n"
                    f"รบกวนขอชื่อ + เบอร์ติดต่อ ทีมงานจะติดต่อกลับครับ\n{contact}")

        return (f"สวัสดีครับ 😊 TON AI Tech ยินดีให้บริการ\n"
                f"เราเชี่ยวชาญ Smart Factory, IoT, CCTV AI, Network, Automation\n"
                f"สนใจเรื่องไหนสอบถามได้เลยครับ\n{contact}")

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


# ─── Rate Limiter — กันยิงถล่ม webhook / เผาโควต้า Gemini ───
_rate_window = []          # timestamps ของ events ล่าสุด
_RATE_MAX_PER_MIN = 30     # สูงสุด 30 events/นาที
_user_rate = {}            # per-user: {user_id: [timestamps]}
_USER_MAX_PER_MIN = 8      # user เดียวสูงสุด 8 ข้อความ/นาที


def _rate_ok(user_id: str = "") -> bool:
    now = time.time()
    # global
    global _rate_window
    _rate_window = [t for t in _rate_window if now - t < 60]
    if len(_rate_window) >= _RATE_MAX_PER_MIN:
        return False
    _rate_window.append(now)
    # per-user
    if user_id:
        lst = [t for t in _user_rate.get(user_id, []) if now - t < 60]
        if len(lst) >= _USER_MAX_PER_MIN:
            _user_rate[user_id] = lst
            return False
        lst.append(now)
        _user_rate[user_id] = lst
        if len(_user_rate) > 500:   # กัน dict โตไม่จำกัด
            _user_rate.clear()
    return True


def handle_webhook(config, body_bytes: bytes, signature: str) -> dict:
    """Entry point — เรียกจาก Flask webhook route"""
    # กัน payload ใหญ่ผิดปกติ
    if len(body_bytes) > 512 * 1024:
        return {"status": "too_large"}

    handler = LineAIReply(config)

    # Verify signature (ข้ามเฉพาะตอนไม่ได้ตั้ง LINE_CHANNEL_SECRET)
    if not handler.verify_signature(body_bytes, signature):
        logger.warning("LINE webhook signature invalid — rejected")
        return {"status": "invalid_signature"}

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {"status": "bad_json"}

    events = data.get("events", [])
    if not isinstance(events, list):
        return {"status": "bad_payload"}

    for event in events[:10]:   # จำกัด 10 events/request
        try:
            uid = event.get("source", {}).get("userId", "")
            if not _rate_ok(uid):
                logger.warning(f"Rate limit hit (user {uid[:8]}) — skipped")
                continue
            handler.handle_message_event(event)
        except Exception as e:
            logger.error(f"handle event error: {e}")

    return {"status": "ok"}
