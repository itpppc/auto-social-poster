# -*- coding: utf-8 -*-
"""
Cloudflare Tunnel Manager — เปิด public URL ให้ LINE webhook เข้าถึง localhost:5001
- ใช้ Quick Tunnel (trycloudflare.com) ฟรี ไม่ต้องสมัคร
- URL เปลี่ยนทุกครั้งที่ restart → บันทึกลงไฟล์ + RTDB ให้ดูได้จาก dashboard
- Auto-restart ถ้า tunnel หลุด
"""
import logging
import re
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent
CLOUDFLARED = BASE / "cloudflared.exe"
URL_FILE = BASE / "tunnel_url.txt"

_current_url = None
_process = None


def get_tunnel_url() -> str:
    """คืน URL ปัจจุบันของ tunnel (อ่านจากไฟล์)"""
    global _current_url
    if _current_url:
        return _current_url
    if URL_FILE.exists():
        return URL_FILE.read_text(encoding="utf-8").strip()
    return ""


def _save_url(url: str):
    global _current_url
    _current_url = url
    URL_FILE.write_text(url, encoding="utf-8")
    logger.info(f"Tunnel URL: {url}")
    logger.info(f"LINE Webhook URL: {url}/line/webhook")

    # Push ขึ้น RTDB ให้เห็นบน dashboard
    try:
        import firestore_sync as fs
        if fs._init():
            fs._db.reference("config/tunnel_url",
                url="https://ton-ai-tech-default-rtdb.asia-southeast1.firebasedatabase.app"
            ).set({"url": url, "webhook": f"{url}/line/webhook",
                   "updated": time.strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as e:
        logger.warning(f"push tunnel url to RTDB failed: {e}")


def run_tunnel(port: int = 5001):
    """รัน cloudflared quick tunnel — blocking (เรียกใน thread/watchdog)"""
    global _process

    if not CLOUDFLARED.exists():
        logger.error(f"cloudflared.exe ไม่พบที่ {CLOUDFLARED}")
        return

    while True:
        logger.info("Starting Cloudflare tunnel...")
        try:
            _process = subprocess.Popen(
                [str(CLOUDFLARED), "tunnel", "--url", f"http://localhost:{port}",
                 "--no-autoupdate"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )

            url_found = False
            for line in _process.stdout:
                line = line.strip()
                # หา URL จาก output: https://xxxx.trycloudflare.com
                m = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
                if m and not url_found:
                    _save_url(m.group(1))
                    url_found = True
                if "error" in line.lower() and "failed" in line.lower():
                    logger.warning(f"tunnel: {line[:150]}")

            # process จบ = tunnel หลุด
            code = _process.wait()
            logger.warning(f"Tunnel exited (code {code}) — restart in 10s")
        except Exception as e:
            logger.error(f"Tunnel error: {e}")

        time.sleep(10)


def start_in_background(port: int = 5001):
    t = threading.Thread(target=run_tunnel, args=(port,), daemon=True, name="Tunnel")
    t.start()
    return t
