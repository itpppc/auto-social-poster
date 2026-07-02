# -*- coding: utf-8 -*-
"""
Local Image Pool — ดึงรูปที่ user เตรียมไว้เอง ไปโพสก่อน AI gen

โครงสร้าง:
  my_images/
    <page_id หรือ keyword>/    <- รูปของ page นี้
      01.jpg, 02.jpg, ...
    _default/                   <- รูป fallback ทั่วไป

Logic:
  1. เลือกรูปตาม page_id ก่อน (โฟลเดอร์ชื่อ page_id)
  2. ถ้าไม่มี → หาจาก keyword ใน niche (โฟลเดอร์ชื่อ keyword)
  3. ถ้าไม่มี → _default
  4. รูปที่ใช้แล้ว บันทึกใน .used.json — วนใช้เมื่อครบ
  5. คืน None ถ้าไม่มีรูปเลย → ให้ระบบ fallback ไป AI gen
"""
import json
import logging
import random
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent / "my_images"
USED_FILE = BASE_DIR / ".used.json"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}

# map keyword → folder name (ปรับได้)
KEYWORD_FOLDERS = {
    "ขนมจีนทะเลสด": ["อาหารทะเล", "ขนมจีน", "อาหารใต้", "seafood", "น้ำยา"],
    "สลัดคลีน":     ["สลัด", "คลีน", "ผักออร์แกนิค", "ไฮโดรโปนิค", "organic", "delivery"],
    "ขายไอที":      ["ไอที", "คอมพิวเตอร์", "โน๊ตบุ๊ค", "laptop", "it", "server"],
    "การตลาด":      ["การตลาด", "social media", "marketing", "ads", "facebook ads"],
}


def _load_used() -> dict:
    if USED_FILE.exists():
        try:
            return json.loads(USED_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_used(data: dict):
    try:
        USED_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"save used.json failed: {e}")


def _list_images(folder: Path) -> list:
    if not folder.exists():
        return []
    return sorted([f for f in folder.iterdir()
                   if f.is_file() and f.suffix.lower() in IMG_EXT])


def _resolve_folder(page_id: str, niche: str) -> Optional[Path]:
    """หาโฟลเดอร์ที่มีรูปสำหรับ page นี้"""
    # 1. โฟลเดอร์ชื่อ page_id ตรงๆ
    if page_id:
        p = BASE_DIR / page_id
        if _list_images(p):
            return p

    # 2. หาจาก keyword ใน niche
    niche_lower = (niche or "").lower()
    for folder_name, keywords in KEYWORD_FOLDERS.items():
        if any(k.lower() in niche_lower for k in keywords):
            p = BASE_DIR / folder_name
            if _list_images(p):
                return p

    # 3. ลองจับชื่อโฟลเดอร์ตรงกับ niche keyword
    for sub in BASE_DIR.iterdir():
        if sub.is_dir() and sub.name != "_default":
            if sub.name.lower() in niche_lower or any(
                w in niche_lower for w in sub.name.lower().split()):
                if _list_images(sub):
                    return sub

    # 4. _default
    p = BASE_DIR / "_default"
    if _list_images(p):
        return p

    return None


def get_local_image(page_id: str = "", niche: str = "") -> Optional[str]:
    """คืน path ของรูปที่ user เตรียมไว้ (ยังไม่ถูกใช้) หรือ None
    เลือกแบบวนรอบ: ใช้รูปที่ยังไม่ถูกใช้ก่อน ครบแล้ว reset
    """
    folder = _resolve_folder(page_id, niche)
    if not folder:
        return None

    images = _list_images(folder)
    if not images:
        return None

    used = _load_used()
    key = folder.name
    used_list = used.get(key, [])

    # รูปที่ยังไม่ถูกใช้
    unused = [str(f) for f in images if str(f) not in used_list]

    if not unused:
        # ครบรอบ — reset แล้วใช้ใหม่
        used_list = []
        unused = [str(f) for f in images]
        logger.info(f"Image pool '{key}' cycled — reset used list")

    chosen = random.choice(unused)
    used_list.append(chosen)
    used[key] = used_list
    _save_used(used)

    logger.info(f"Local image selected: {Path(chosen).name} (folder: {key})")
    return chosen


def count_images() -> dict:
    """นับรูปในแต่ละโฟลเดอร์ — สำหรับ dashboard/status"""
    result = {}
    if not BASE_DIR.exists():
        return result
    for sub in BASE_DIR.iterdir():
        if sub.is_dir():
            n = len(_list_images(sub))
            if n > 0:
                result[sub.name] = n
    return result
