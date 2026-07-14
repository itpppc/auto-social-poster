# -*- coding: utf-8 -*-
"""
Facebook Messenger AI Auto-Reply — AI ตอบลูกค้าใน Messenger แทนคน
ใช้ AI brain เดียวกับ LINE (IT/IoT/Automation expert)
รองรับหลาย Page — เลือก token ตาม page id ที่ webhook แจ้งมา
"""
import os
import json
import hmac
import hashlib
import logging
import time

import requests

logger = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"

# rate limit — กันยิงถล่ม/เผา quota
_rate = []
_user_rate = {}


def _rate_ok(psid=""):
    now = time.time()
    global _rate
    _rate = [t for t in _rate if now - t < 60]
    if len(_rate) >= 40:
        return False
    _rate.append(now)
    if psid:
        lst = [t for t in _user_rate.get(psid, []) if now - t < 60]
        if len(lst) >= 8:
            _user_rate[psid] = lst
            return False
        lst.append(now)
        _user_rate[psid] = lst
        if len(_user_rate) > 500:
            _user_rate.clear()
    return True


class FBMessengerReply:
    def __init__(self, config):
        self.config = config
        self.app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
        # map page_id -> token (จาก FACEBOOK_PAGES)
        self.page_tokens = {p["id"]: p["token"] for p in config.facebook_pages}
        # reuse AI brain จาก LINE
        from line_ai_reply import LineAIReply
        self._brain = LineAIReply(config)

    def verify_signature(self, body: bytes, sig: str) -> bool:
        if not self.app_secret or not sig:
            return True  # dev mode
        expected = "sha256=" + hmac.new(
            self.app_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)

    def send(self, page_id: str, psid: str, text: str):
        token = self.page_tokens.get(page_id)
        if not token:
            logger.warning(f"FB: no token for page {page_id}")
            return
        r = requests.post(
            f"{GRAPH}/me/messages",
            params={"access_token": token},
            json={"recipient": {"id": psid},
                  "messaging_type": "RESPONSE",
                  "message": {"text": text[:2000]}},
            timeout=15,
        )
        if r.status_code != 200:
            logger.error(f"FB send failed: {r.status_code} {r.text[:150]}")

    def send_quick_replies(self, page_id: str, psid: str, text: str):
        """ส่งข้อความ + ปุ่ม Quick Reply"""
        token = self.page_tokens.get(page_id)
        if not token:
            return
        payload = {
            "recipient": {"id": psid},
            "messaging_type": "RESPONSE",
            "message": {
                "text": text[:2000],
                "quick_replies": [
                    {"content_type": "text", "title": "📞 คุยกับเจ้าหน้าที่", "payload": "HUMAN"},
                    {"content_type": "text", "title": "💰 สอบถามราคา", "payload": "PRICE"},
                    {"content_type": "text", "title": "🎬 ดู Demo", "payload": "DEMO"},
                ],
            },
        }
        requests.post(f"{GRAPH}/me/messages", params={"access_token": token},
                      json=payload, timeout=15)

    def handle_message(self, page_id: str, psid: str, text: str):
        if not _rate_ok(psid):
            logger.warning(f"FB rate limit (psid {psid[:8]})")
            return
        logger.info(f"FB msg from {psid[:8]} @page {page_id[-4:]}: {text[:50]}")

        # อยากคุยกับคน → ส่งข้อมูลติดต่อ
        if self._brain.wants_human(text):
            self.send(page_id, psid, self._brain._contact_human_message()["text"])
            return

        # AI ตอบ (ใช้ brain เดียวกับ LINE — knowledge IT/IoT/Automation)
        reply = self._brain.generate_reply(f"fb_{psid}", text)
        self.send_quick_replies(page_id, psid, reply)


def handle_webhook(config, body_bytes: bytes, signature: str) -> dict:
    """POST — ประมวลผลข้อความจากลูกค้า"""
    if len(body_bytes) > 512 * 1024:
        return {"status": "too_large"}

    h = FBMessengerReply(config)
    if not h.verify_signature(body_bytes, signature):
        logger.warning("FB webhook signature invalid")
        return {"status": "invalid_signature"}

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {"status": "bad_json"}

    if data.get("object") != "page":
        return {"status": "ignored"}

    for entry in data.get("entry", [])[:10]:
        page_id = str(entry.get("id", ""))
        for ev in entry.get("messaging", [])[:10]:
            try:
                psid = ev.get("sender", {}).get("id", "")
                msg = ev.get("message", {})
                # ข้าม echo (ข้อความที่ page ส่งเอง) + delivery/read receipts
                if msg.get("is_echo") or not psid:
                    continue
                text = msg.get("text", "")
                if text:
                    h.handle_message(page_id, psid, text)
                elif msg.get("attachments"):
                    h.send(page_id, psid,
                           f"ขอบคุณครับ 😊 มีอะไรให้ช่วยไหมครับ?\n📞 {h._brain.contact_phone}")
            except Exception as e:
                logger.error(f"FB event error: {e}")

    return {"status": "ok"}


def verify_challenge(mode: str, token: str, challenge: str) -> tuple:
    """GET — LINE Console verify webhook (hub.challenge)"""
    verify_token = os.getenv("FB_VERIFY_TOKEN", "tonai_verify_2026")
    if mode == "subscribe" and token == verify_token:
        return challenge, 200
    return "forbidden", 403
