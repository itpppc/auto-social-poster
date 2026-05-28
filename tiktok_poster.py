"""
TikTok Auto Poster — Video Slideshow Upload + Auto-refresh access token
- access_token หมดอายุ 1 วัน → refresh อัตโนมัติด้วย refresh_token
- refresh_token หมดอายุ 365 วัน
"""
import io
import os
import re
import time
import logging
import tempfile
from pathlib import Path

import requests

from content_generator import GeneratedContent
from config import Config

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TOKEN_URL       = "https://open.tiktokapis.com/v2/oauth/token/"
TARGET_W, TARGET_H = 1080, 1920
ENV_PATH = Path(__file__).parent / ".env"


class TikTokPoster:
    def __init__(self, config: Config):
        self.config        = config
        self.access_token  = config.tiktok_access_token
        self.refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN", "")
        try:
            self.token_expires_at = float(os.getenv("TIKTOK_TOKEN_EXPIRES_AT", "0"))
        except ValueError:
            self.token_expires_at = 0

    # ──────────────────────────────────────────────────────
    # TOKEN MANAGEMENT (auto-refresh)
    # ──────────────────────────────────────────────────────
    def _ensure_valid_token(self):
        """Refresh access_token ถ้าหมดอายุหรือใกล้หมด (เหลือ < 1 ชั่วโมง)"""
        if not self.refresh_token:
            logger.warning("TikTok: ไม่มี refresh_token — ไม่สามารถ refresh ได้")
            return

        # If expires_at is 0 (unknown) or within 1 hour buffer, refresh
        buffer_sec = 3600
        if self.token_expires_at == 0 or time.time() >= self.token_expires_at - buffer_sec:
            logger.info("TikTok access_token ใกล้หมดอายุ → refreshing...")
            self._refresh_access_token()

    def _refresh_access_token(self):
        client_key    = os.getenv("TIKTOK_CLIENT_KEY", self.config.tiktok_client_key)
        client_secret = os.getenv("TIKTOK_CLIENT_SECRET", self.config.tiktok_client_secret)

        r = requests.post(TOKEN_URL, data={
            "client_key":    client_key,
            "client_secret": client_secret,
            "grant_type":    "refresh_token",
            "refresh_token": self.refresh_token,
        }, timeout=15)
        result = r.json()

        if "access_token" not in result:
            logger.error(f"TikTok token refresh FAILED: {result}")
            return

        self.access_token     = result["access_token"]
        self.refresh_token    = result.get("refresh_token", self.refresh_token)
        self.token_expires_at = time.time() + result.get("expires_in", 86400)
        self._save_tokens_to_env()
        days = result.get("expires_in", 86400) // 86400
        logger.info(f"✅ TikTok token refreshed — หมดอายุใน {days} วัน")

    def _save_tokens_to_env(self):
        """บันทึก access_token, refresh_token, expires_at กลับเข้า .env"""
        try:
            content = ENV_PATH.read_text(encoding="utf-8")
            updates = {
                "TIKTOK_ACCESS_TOKEN":      self.access_token,
                "TIKTOK_REFRESH_TOKEN":     self.refresh_token,
                "TIKTOK_TOKEN_EXPIRES_AT":  str(int(self.token_expires_at)),
            }
            for key, val in updates.items():
                pattern = rf"{key}=[^\r\n]*"
                if re.search(pattern, content):
                    content = re.sub(pattern, f"{key}={val}", content)
                else:
                    content += f"\n{key}={val}"
            ENV_PATH.write_text(content, encoding="utf-8")
            # Also update env vars for this process
            os.environ["TIKTOK_ACCESS_TOKEN"]     = self.access_token
            os.environ["TIKTOK_REFRESH_TOKEN"]    = self.refresh_token
            os.environ["TIKTOK_TOKEN_EXPIRES_AT"] = str(int(self.token_expires_at))
        except Exception as e:
            logger.error(f"TikTok: บันทึก token ใน .env ไม่สำเร็จ: {e}")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type":  "application/json",
        }

    # ──────────────────────────────────────────────────────
    # VIDEO CREATION
    # ──────────────────────────────────────────────────────
    def _create_slideshow(self, image_urls: list[str],
                          seconds_per_image: int = 3, fps: int = 24) -> tuple[str, int]:
        import imageio
        import numpy as np
        from PIL import Image

        output_path = Path(tempfile.gettempdir()) / "tonai_tiktok.mp4"
        writer = imageio.get_writer(
            str(output_path), fps=fps, codec="libx264",
            output_params=["-pix_fmt", "yuv420p", "-crf", "28"],
        )
        for url in image_urls:
            try:
                resp = requests.get(url, timeout=15)
                img  = Image.open(io.BytesIO(resp.content)).convert("RGB")
                w, h = img.size
                ratio = TARGET_W / TARGET_H
                if (w / h) > ratio:
                    nw = int(h * ratio)
                    img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
                else:
                    nh = int(w / ratio)
                    img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
                img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
                frame = np.array(img)
                for _ in range(fps * seconds_per_image):
                    writer.append_data(frame)
            except Exception as e:
                logger.warning(f"Skip image {url[:50]}: {e}")
        writer.close()
        size = output_path.stat().st_size
        logger.info(f"Slideshow created: {size // 1024} KB, {len(image_urls)} images")
        return str(output_path), size

    # ──────────────────────────────────────────────────────
    # POST METHODS
    # ──────────────────────────────────────────────────────
    def post_photo_mode(self, content: GeneratedContent, image_urls: list[str]) -> dict:
        if not self.access_token:
            raise ValueError("ต้องตั้งค่า TIKTOK_ACCESS_TOKEN")
        if not image_urls:
            raise ValueError("ไม่มี image URLs")

        self._ensure_valid_token()
        video_path, video_size = self._create_slideshow(image_urls[:5], seconds_per_image=3)
        return self._upload_video_file(content, video_path, video_size)

    def upload_video(self, content: GeneratedContent, video_path: str) -> dict:
        if not self.access_token:
            raise ValueError("ต้องตั้งค่า TIKTOK_ACCESS_TOKEN")
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"ไม่พบไฟล์ video: {video_path}")

        self._ensure_valid_token()
        size = os.path.getsize(video_path)
        return self._upload_video_file(content, video_path, size)

    def _upload_video_file(self, content: GeneratedContent,
                           video_path: str, video_size: int) -> dict:
        title = getattr(content, "tiktok_script", content.topic)
        title = (title or content.topic)[:150]

        init_payload = {
            "post_info": {
                "title":           title,
                "privacy_level":   "SELF_ONLY",
                "disable_duet":    False,
                "disable_comment": False,
                "disable_stitch":  False,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        video_size,
                "chunk_size":        video_size,
                "total_chunk_count": 1,
            },
        }
        r = requests.post(f"{TIKTOK_API_BASE}/post/publish/video/init/",
                          headers=self._headers(), json=init_payload, timeout=30)
        init_data = r.json()

        err = init_data.get("error", {})
        if err.get("code") != "ok":
            # If token expired despite our buffer, try one more refresh
            if err.get("code") in ("access_token_invalid", "access_token_expired") and self.refresh_token:
                logger.warning("Token rejected, force-refreshing...")
                self._refresh_access_token()
                r = requests.post(f"{TIKTOK_API_BASE}/post/publish/video/init/",
                                  headers=self._headers(), json=init_payload, timeout=30)
                init_data = r.json()
                err = init_data.get("error", {})
                if err.get("code") != "ok":
                    raise Exception(f"TikTok init failed: {init_data}")
            else:
                raise Exception(f"TikTok init failed: {init_data}")

        publish_id = init_data["data"]["publish_id"]
        upload_url = init_data["data"]["upload_url"]

        with open(video_path, "rb") as f:
            video_data = f.read()
        upload_headers = {
            "Content-Range":  f"bytes 0-{video_size-1}/{video_size}",
            "Content-Type":   "video/mp4",
            "Content-Length": str(video_size),
        }
        r2 = requests.put(upload_url, headers=upload_headers, data=video_data, timeout=120)
        if r2.status_code not in [200, 201, 206]:
            raise Exception(f"TikTok upload failed: HTTP {r2.status_code}")

        logger.info(f"TikTok video uploaded, publish_id: {publish_id}")
        return {"platform": "tiktok", "status": "success", "publish_id": publish_id}

    def check_publish_status(self, publish_id: str) -> dict:
        r = requests.post(f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
                          headers=self._headers(), json={"publish_id": publish_id},
                          timeout=30)
        return r.json()
