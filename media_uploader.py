# -*- coding: utf-8 -*-
"""
Media Uploader — upload local file → public HTTPS URL
สำหรับใช้กับ LINE/TikTok ที่ต้องการ public URL
ใช้ catbox.moe (ฟรี ไม่ต้อง key)
"""
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def upload_to_catbox(file_path: str) -> Optional[str]:
    """อัปโหลดไฟล์ → catbox.moe → คืน public URL (HTTPS)"""
    fp = Path(file_path)
    if not fp.exists():
        logger.error(f"File not found: {file_path}")
        return None

    try:
        with open(fp, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (fp.name, f)},
                timeout=120,
            )
        if r.status_code == 200 and r.text.startswith("https://"):
            url = r.text.strip()
            logger.info(f"Uploaded to catbox: {url} ({fp.stat().st_size//1024} KB)")
            return url
        logger.error(f"catbox upload failed: {r.status_code} {r.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"catbox upload error: {e}")
        return None


def upload_to_litterbox(file_path: str, expire: str = "24h") -> Optional[str]:
    """Litterbox = temporary catbox (1h/12h/24h/72h) — ใช้สำหรับ media ชั่วคราว"""
    fp = Path(file_path)
    if not fp.exists():
        return None
    try:
        with open(fp, "rb") as f:
            r = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": expire},
                files={"fileToUpload": (fp.name, f)},
                timeout=120,
            )
        if r.status_code == 200 and r.text.startswith("https://"):
            return r.text.strip()
        return None
    except Exception as e:
        logger.error(f"litterbox error: {e}")
        return None


def upload_media(file_path: str, permanent: bool = False) -> Optional[str]:
    """อัปโหลดไฟล์ → public URL
    permanent=True → catbox (ถาวร), False → litterbox (24h)
    """
    if permanent:
        return upload_to_catbox(file_path)
    return upload_to_litterbox(file_path) or upload_to_catbox(file_path)
