# -*- coding: utf-8 -*-
"""
Catch-up Posting — โพสต์ชดเชยรอบที่ขาด (เครื่องปิด/service ตายตอนถึงเวลาโพสต์)

ใช้โดย scheduler.py ตอน service เริ่ม:
  cfg = load_catchup_config()
  missed = find_missed_slots(post_times, max_age_hours=, grace_minutes=)
  run_catchup_async(workflow, post_times, max_age_hours=, delay_seconds=, grace_minutes=)

ตรวจว่า slot ไหน "โพสต์แล้ว" จากไฟล์ post_logs/post_YYYYMMDD_HHMMSS.json
กันโพสต์ spam: ชดเชยสูงสุด CATCHUP_MAX_POSTS รอบ (default 1 = เอารอบล่าสุดที่ขาด)
"""
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent / "post_logs"
_FNAME_RE = re.compile(r"post_(\d{8})_(\d{6})")


def load_catchup_config() -> dict:
    """อ่านค่าจาก env — default: เปิด, ย้อนหลัง 12 ชม., grace 10 นาที, delay 60 วิ, ชดเชยสูงสุด 1 รอบ"""
    def _int(name, default):
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    return {
        "enabled": os.getenv("ENABLE_CATCHUP", "true").strip().lower() != "false",
        "max_age_hours": _int("CATCHUP_MAX_AGE_HOURS", 12),
        "grace_minutes": _int("CATCHUP_GRACE_MINUTES", 10),
        "delay_seconds": _int("CATCHUP_DELAY_SECONDS", 60),
        "max_posts": _int("CATCHUP_MAX_POSTS", 1),
    }


def _posted_datetimes() -> list:
    """เวลาโพสต์จริงทั้งหมด จากชื่อไฟล์ใน post_logs/"""
    result = []
    if not LOG_DIR.exists():
        return result
    for f in LOG_DIR.glob("post_*.json"):
        m = _FNAME_RE.search(f.name)
        if not m:
            continue
        try:
            result.append(datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"))
        except ValueError:
            continue
    return result


def find_missed_slots(post_times: list, max_age_hours: int = 12,
                      grace_minutes: int = 10) -> list:
    """คืน list[datetime] ของ slot ที่เลยเวลาแล้ว (เกิน grace) แต่ไม่มีโพสต์จริง
    ดูเฉพาะ slot ภายใน max_age_hours ที่ผ่านมา (วันนี้และเมื่อวานถ้าอยู่ใน window)
    slot ถือว่า 'โพสต์แล้ว' ถ้ามีไฟล์ log เวลาใดๆ ใน [slot, slot+90 นาที]
    """
    now = datetime.now()
    window_start = now - timedelta(hours=max_age_hours)
    posted = _posted_datetimes()

    missed = []
    for day_offset in (1, 0):  # เมื่อวานก่อน แล้ววันนี้ (เรียงเก่า→ใหม่)
        day = (now - timedelta(days=day_offset)).date()
        for t in post_times:
            try:
                hh, mm = t.strip().split(":")
                slot = datetime.combine(day, datetime.min.time()).replace(
                    hour=int(hh), minute=int(mm))
            except (ValueError, AttributeError):
                continue
            # ต้องเลยเวลา slot + grace แล้ว และอยู่ใน window
            if slot + timedelta(minutes=grace_minutes) > now:
                continue
            if slot < window_start:
                continue
            # มีโพสต์จริงใน slot นี้แล้วหรือยัง
            covered = any(slot <= p <= slot + timedelta(minutes=90) for p in posted)
            if not covered:
                missed.append(slot)

    return sorted(missed)


def _catchup_worker(workflow, slots: list, delay_seconds: int):
    for i, slot in enumerate(slots):
        if i > 0:
            time.sleep(delay_seconds)
        label = slot.strftime("%H:%M")
        logger.info(f"[CATCHUP] โพสต์ชดเชยรอบ {label} ...")
        try:
            workflow.run(trigger=f"catchup_{label}")
            logger.info(f"[CATCHUP] รอบ {label} เสร็จ")
        except Exception as e:
            logger.error(f"[CATCHUP] รอบ {label} ล้มเหลว: {e}")


def run_catchup_async(workflow, post_times: list, max_age_hours: int = 12,
                      delay_seconds: int = 60, grace_minutes: int = 10):
    """โพสต์ชดเชยใน daemon thread — เลือกรอบล่าสุดที่ขาดตาม max_posts (default 1)"""
    cfg = load_catchup_config()
    missed = find_missed_slots(post_times, max_age_hours=max_age_hours,
                               grace_minutes=grace_minutes)
    if not missed:
        return None

    slots = missed[-cfg["max_posts"]:]  # เอารอบล่าสุด กัน spam
    skipped = len(missed) - len(slots)
    if skipped > 0:
        logger.info(f"[CATCHUP] ขาด {len(missed)} รอบ — ชดเชยเฉพาะ {len(slots)} รอบล่าสุด "
                    f"(ข้าม {skipped} รอบเก่า กันโพสต์ถี่)")

    t = threading.Thread(target=_catchup_worker, args=(workflow, slots, delay_seconds),
                         daemon=True, name="CatchupWorker")
    t.start()
    return t
