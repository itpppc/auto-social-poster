"""
Real-time status tracker — เขียนสถานะปัจจุบันลง JSON file
ให้ dashboard polling อ่านเพื่อแสดง n8n-style flow
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_STATUS_FILE = Path(__file__).parent / "current_status.json"
_LOCK = threading.Lock()

# stages: idle, generating, image_search, facebook, line, tiktok, done
_DEFAULT = {
    "running": False,
    "stage": "idle",
    "started_at": None,
    "finished_at": None,
    "topic": "",
    "source": "",
    "preview": {
        "facebook_pages": [],   # [{page_id, page_name, niche, text, hashtags, image_url, status, error}]
        "line": {"text": "", "status": "pending", "error": ""},
        "tiktok": {"text": "", "status": "pending", "error": ""},
    },
    "log": [],   # [{ts, level, message}]
}


def _read() -> dict:
    if not _STATUS_FILE.exists():
        return dict(_DEFAULT)
    try:
        with open(_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(_DEFAULT)


def _write(data: dict):
    with _LOCK:
        with open(_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    # Push to Firestore (silent fail if not configured)
    try:
        import firestore_sync
        firestore_sync.sync_current_status(data)
    except Exception:
        pass


def start_run(trigger: str = "scheduled"):
    """เริ่มรอบโพสต์ใหม่ — รีเซ็ตทุกอย่าง"""
    data = dict(_DEFAULT)
    data["running"]    = True
    data["stage"]      = "generating"
    data["started_at"] = datetime.now().isoformat()
    data["trigger"]    = trigger
    data["log"]        = [{"ts": data["started_at"], "level": "info", "message": f"🚀 เริ่มรอบโพสต์ ({trigger})"}]
    _write(data)


def set_topic(topic: str, source: str):
    data = _read()
    data["topic"]  = topic
    data["source"] = source
    data["stage"]  = "preview_ready"
    log(f"📝 หัวข้อ: {topic[:80]}", "info")


def set_facebook_preview(pages: list):
    """pages = [{page_id, page_name, niche, text, hashtags, image_url}]"""
    data = _read()
    for pg in pages:
        pg.setdefault("status", "pending")
        pg.setdefault("error", "")
    data["preview"]["facebook_pages"] = pages
    _write(data)


def set_line_preview(text: str):
    data = _read()
    data["preview"]["line"]["text"] = text
    _write(data)


def set_tiktok_preview(text: str):
    data = _read()
    data["preview"]["tiktok"]["text"] = text
    _write(data)


def set_stage(stage: str):
    data = _read()
    data["stage"] = stage
    _write(data)
    log(f"➡️  Stage: {stage}", "info")


def update_facebook_status(page_id: str, status: str, error: str = ""):
    data = _read()
    for pg in data["preview"]["facebook_pages"]:
        if pg["page_id"] == page_id:
            pg["status"] = status
            pg["error"]  = error
            break
    _write(data)
    emoji = "✅" if status == "success" else "❌"
    log(f"{emoji} Facebook [{page_id[-4:]}]: {status}" + (f" — {error[:120]}" if error else ""),
        "success" if status == "success" else "error")


def update_line_status(status: str, error: str = ""):
    data = _read()
    data["preview"]["line"]["status"] = status
    data["preview"]["line"]["error"]  = error
    _write(data)
    emoji = "✅" if status == "success" else "❌"
    log(f"{emoji} LINE: {status}" + (f" — {error[:120]}" if error else ""),
        "success" if status == "success" else "error")


def update_tiktok_status(status: str, error: str = ""):
    data = _read()
    data["preview"]["tiktok"]["status"] = status
    data["preview"]["tiktok"]["error"]  = error
    _write(data)
    emoji = "✅" if status == "success" else "❌"
    log(f"{emoji} TikTok: {status}" + (f" — {error[:120]}" if error else ""),
        "success" if status == "success" else "error")


def finish_run():
    data = _read()
    data["running"]     = False
    data["stage"]       = "done"
    data["finished_at"] = datetime.now().isoformat()
    _write(data)
    log("🏁 จบรอบโพสต์", "info")


def log(message: str, level: str = "info"):
    data = _read()
    entry = {"ts": datetime.now().isoformat(), "level": level, "message": message}
    data["log"] = (data.get("log", []) + [entry])[-50:]
    _write(data)


def get_status() -> dict:
    return _read()
