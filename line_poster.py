"""
LINE Messaging API Auto Poster
LINE Notify ถูกปิดแล้วตั้งแต่ March 2025
ใช้ LINE Messaging API (Official Account) แทน

ขั้นตอนรับ token:
1. สมัคร LINE OA: https://manager.line.biz/
2. ไป LINE Developers: https://developers.line.biz/
3. สร้าง Messaging API channel
4. Issue Channel Access Token (long-lived)

FREE plan: 200 messages/เดือน
"""
import requests
import logging
from content_generator import GeneratedContent
from config import Config

logger = logging.getLogger(__name__)

API_BASE = "https://api.line.me/v2/bot"


class LinePoster:
    def __init__(self, config: Config):
        self.token = config.line_channel_access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _clean_text(self, text: str) -> str:
        """ล้าง control chars + invalid Unicode ที่ทำให้ LINE แสดงเป็นภาษาแปลก"""
        if not text: return ""
        import re
        # 1. Strip control chars (เก็บ \n \r \t)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # 2. Strip zero-width chars (ตัวล่องหน)
        text = re.sub(r'[​-‏‪-‮⁠-⁯﻿]', '', text)
        # 3. Normalize Unicode
        import unicodedata
        text = unicodedata.normalize('NFC', text)
        return text.strip()

    def broadcast_text(self, text: str) -> dict:
        """Broadcast ข้อความ raw text"""
        if not self.token:
            raise ValueError("ต้องตั้งค่า LINE_CHANNEL_ACCESS_TOKEN ใน .env")
        text = self._clean_text(text)
        payload = {"messages": [{"type": "text", "text": text[:5000]}]}
        r = requests.post(f"{API_BASE}/message/broadcast",
                          headers=self._headers(), json=payload, timeout=30)
        if r.status_code != 200:
            raise Exception(f"LINE broadcast failed: {r.status_code} {r.text}")
        return {"platform": "line", "status": "success"}

    def broadcast_with_media(self, text: str, media_url: str,
                              media_type: str = "image",
                              preview_url: str = None) -> dict:
        """Broadcast ข้อความ + รูป/วีดีโอ"""
        if not self.token:
            raise ValueError("ต้องตั้งค่า LINE_CHANNEL_ACCESS_TOKEN ใน .env")

        text = self._clean_text(text)
        messages = []
        if text:
            messages.append({"type": "text", "text": text[:5000]})

        if media_type == "image":
            messages.append({
                "type": "image",
                "originalContentUrl": media_url,
                "previewImageUrl": preview_url or media_url,
            })
        elif media_type == "video":
            messages.append({
                "type": "video",
                "originalContentUrl": media_url,
                "previewImageUrl": preview_url or media_url,
            })

        payload = {"messages": messages[:5]}
        r = requests.post(f"{API_BASE}/message/broadcast",
                          headers=self._headers(), json=payload, timeout=60)
        if r.status_code != 200:
            raise Exception(f"LINE media broadcast failed: {r.status_code} {r.text[:300]}")
        return {"platform": "line", "status": "success", "media_type": media_type}

    def broadcast(self, content: GeneratedContent) -> dict:
        """Broadcast ข้อความธรรมดาถึง followers ทั้งหมด"""
        if not self.token:
            raise ValueError("ต้องตั้งค่า LINE_CHANNEL_ACCESS_TOKEN ใน .env")

        hashtags_str = " ".join(content.hashtags)
        text = self._clean_text(f"{content.line_message}\n\n{hashtags_str}\n\n{content.call_to_action}")

        payload = {
            "messages": [{"type": "text", "text": text[:5000]}]
        }

        response = requests.post(
            f"{API_BASE}/message/broadcast",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"LINE Broadcast ล้มเหลว: {response.status_code} — {response.text}")

        logger.info("LINE Broadcast สำเร็จ")
        return {"platform": "line", "status": "success"}

    def broadcast_flex(self, content: GeneratedContent) -> dict:
        """Broadcast แบบ Flex Message (card สวยงาม)"""
        if not self.token:
            raise ValueError("ต้องตั้งค่า LINE_CHANNEL_ACCESS_TOKEN ใน .env")

        # Clean ทุก text field
        topic = self._clean_text(content.topic)
        line_msg = self._clean_text(content.line_message)
        cta = self._clean_text(content.call_to_action)
        hashtags = self._clean_text(" ".join(content.hashtags or []))

        flex_message = {
            "type": "flex",
            "altText": topic[:400],
            "contents": {
                "type": "bubble",
                "size": "mega",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#1D4ED8",
                    "paddingAll": "lg",
                    "contents": [
                        {
                            "type": "text",
                            "text": topic[:200],
                            "color": "#FFFFFF",
                            "weight": "bold",
                            "size": "md",
                            "wrap": True,
                        }
                    ],
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": line_msg[:2000],
                            "wrap": True,
                            "size": "sm",
                            "color": "#374151",
                        },
                        {"type": "separator"},
                        {
                            "type": "text",
                            "text": hashtags[:500],
                            "wrap": True,
                            "size": "xs",
                            "color": "#2563EB",
                        },
                    ],
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#1D4ED8",
                            "action": {
                                "type": "message",
                                "label": cta[:20],
                                "text": cta[:20],
                            },
                        }
                    ],
                },
            },
        }

        payload = {"messages": [flex_message]}
        response = requests.post(
            f"{API_BASE}/message/broadcast",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"LINE Flex Broadcast ล้มเหลว: {response.status_code} — {response.text}")

        logger.info("LINE Flex Broadcast สำเร็จ")
        return {"platform": "line_flex", "status": "success"}

    def get_follower_count(self) -> int:
        """ดูจำนวน followers"""
        response = requests.get(
            f"{API_BASE}/followers/count",
            headers=self._headers(),
            timeout=30,
        )
        data = response.json()
        return data.get("count", 0)
