"""
Configuration — โหลดจาก .env อัตโนมัติ
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # ===== GEMINI API (ฟรี) =====
    # สมัครที่: https://aistudio.google.com/
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

    # ===== FACEBOOK (รองรับหลาย Page) =====
    # FACEBOOK_PAGES=id1:token1,id2:token2
    facebook_page_id: str = field(default_factory=lambda: os.getenv("FACEBOOK_PAGE_ID", ""))
    facebook_access_token: str = field(default_factory=lambda: os.getenv("FACEBOOK_ACCESS_TOKEN", ""))

    @property
    def facebook_pages(self) -> list[dict]:
        pages_env = os.getenv("FACEBOOK_PAGES", "")
        if pages_env:
            pages = []
            for entry in pages_env.split(","):
                parts = entry.strip().split(":", 2)
                if len(parts) >= 2:
                    pages.append({
                        "id": parts[0],
                        "token": parts[1],
                        "niche": parts[2] if len(parts) == 3 else self.content_niche,
                    })
            return pages
        if self.facebook_page_id and self.facebook_access_token:
            return [{"id": self.facebook_page_id, "token": self.facebook_access_token, "niche": self.content_niche}]
        return []

    # ===== LINE Messaging API =====
    # สมัครที่: https://developers.line.biz/
    line_channel_access_token: str = field(default_factory=lambda: os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""))

    # ===== PEXELS (รูปภาพ — ฟรี) =====
    # สมัคร: https://www.pexels.com/api/
    pexels_api_key: str = field(default_factory=lambda: os.getenv("PEXELS_API_KEY", ""))

    # ===== TIKTOK (optional) =====
    tiktok_client_key: str = field(default_factory=lambda: os.getenv("TIKTOK_CLIENT_KEY", ""))
    tiktok_client_secret: str = field(default_factory=lambda: os.getenv("TIKTOK_CLIENT_SECRET", ""))
    tiktok_access_token: str = field(default_factory=lambda: os.getenv("TIKTOK_ACCESS_TOKEN", ""))

    # ===== CONTENT =====
    content_niche: str = field(default_factory=lambda: os.getenv("CONTENT_NICHE", "ความรู้การเงินและการลงทุน"))
    line_content_niche: str = field(default_factory=lambda: os.getenv("LINE_CONTENT_NICHE", ""))

    # ===== PLATFORMS =====
    enable_facebook: bool = field(default_factory=lambda: os.getenv("ENABLE_FACEBOOK", "true").lower() == "true")
    enable_line: bool = field(default_factory=lambda: os.getenv("ENABLE_LINE", "true").lower() == "true")
    enable_tiktok: bool = field(default_factory=lambda: os.getenv("ENABLE_TIKTOK", "false").lower() == "true")

    # ===== SCHEDULE =====
    post_times: List[str] = field(default_factory=lambda: [
        t.strip() for t in os.getenv("POST_TIMES", "08:00,12:00,17:00,21:00").split(",")
    ])

    # ===== LOGGING =====
    log_file: str = "auto_poster.log"
    log_level: str = "INFO"
