# -*- coding: utf-8 -*-
"""
Firebase Realtime Database Sync — บันทึก post logs และ status ขึ้น cloud
ใช้ RTDB (Realtime Database) ที่ ton-ai-tech-default-rtdb.asia-southeast1
"""
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_URL = "https://ton-ai-tech-default-rtdb.asia-southeast1.firebasedatabase.app/"

_db = None
_initialized = False
_init_failed = False


def _init():
    global _db, _initialized, _init_failed
    if _initialized or _init_failed:
        return _db is not None

    try:
        import firebase_admin
        from firebase_admin import credentials, db

        cred_path = Path(__file__).parent / "firebase-service-account.json"
        if not cred_path.exists():
            logger.warning("RTDB: firebase-service-account.json ไม่พบ → skip sync")
            _init_failed = True
            return False

        if not firebase_admin._apps:
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

        _db = db
        _initialized = True
        logger.info("Firebase RTDB: เชื่อมต่อสำเร็จ")
        return True
    except Exception as e:
        logger.warning(f"RTDB init failed: {e}")
        _init_failed = True
        return False


def sync_post_log(log_data: dict):
    """บันทึก post log ลง /posts/{doc_id}"""
    if not _init():
        return
    try:
        ts = log_data.get("timestamp", datetime.now().isoformat())
        doc_id = ts.replace(":", "_").replace(".", "_").replace("-", "_")
        _db.reference(f"posts/{doc_id}").set(log_data)
    except Exception as e:
        logger.error(f"RTDB sync_post_log error: {e}")


def sync_current_status(status_data: dict):
    """อัปเดต current status realtime"""
    if not _init():
        return
    try:
        _db.reference("status/current").set(status_data)
    except Exception as e:
        logger.error(f"RTDB sync_current_status error: {e}")


def sync_stats(stats: dict):
    if not _init():
        return
    try:
        stats["updated_at"] = datetime.now().isoformat()
        _db.reference("stats/summary").set(stats)
    except Exception as e:
        logger.error(f"RTDB sync_stats error: {e}")


def is_available() -> bool:
    return _init()
