# -*- coding: utf-8 -*-
"""
Image Resizer — ปรับขนาดรูปอัตโนมัติตาม spec ของแต่ละ platform
รองรับรูปที่ user ใส่เอง (my_images/) ให้เหมาะกับ FB/LINE/TikTok

Platform specs:
  Facebook Feed:  1200 x 630  (1.91:1 แนวนอน)
  Facebook Square:1080 x 1080 (1:1)
  LINE Image:     1040 x 1040 (1:1, max 10MB)
  TikTok Video:   1080 x 1920 (9:16 แนวตั้ง)

วิธี: smart crop (crop ตรงกลาง) + resize + pad ถ้าจำเป็น
"""
import io
import logging
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Platform specs: (width, height)
SPECS = {
    "facebook":        (1200, 630),   # FB feed แนวนอน
    "facebook_square": (1080, 1080),  # FB จตุรัส
    "line":            (1040, 1040),  # LINE รูป
    "tiktok":          (1080, 1920),  # TikTok แนวตั้ง 9:16
    "instagram":       (1080, 1080),  # IG feed
}


def _smart_crop_resize(img, target_w: int, target_h: int, pad_mode: bool = False):
    """crop ตรงกลางให้ได้อัตราส่วน แล้ว resize
    pad_mode=True → ไม่ crop แต่เติมขอบ (เหมาะกับรูปที่ไม่อยากตัด เช่น สินค้า)
    """
    from PIL import Image, ImageFilter

    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if pad_mode:
        # Scale ให้ fit ในกรอบ + เติมขอบ blur จากรูปเดิม
        scale = min(target_w / src_w, target_h / src_h)
        new_w, new_h = int(src_w * scale), int(src_h * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        # พื้นหลัง = รูปเดิม blur ขยายเต็มกรอบ
        bg = img.resize((target_w, target_h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(30))
        # วางรูปตรงกลาง
        offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
        bg.paste(resized, offset)
        return bg
    else:
        # Smart crop — crop ให้ได้ ratio แล้ว resize
        if src_ratio > target_ratio:
            # รูปกว้างเกิน → crop ซ้าย-ขวา
            new_w = int(src_h * target_ratio)
            left = (src_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, src_h))
        else:
            # รูปสูงเกิน → crop บน-ล่าง (เก็บส่วนกลางค่อนบน สำหรับอาหาร/สินค้า)
            new_h = int(src_w / target_ratio)
            top = int((src_h - new_h) * 0.35)  # เก็บส่วนบนมากกว่า (หัวอาหาร/สินค้า)
            img = img.crop((0, top, src_w, top + new_h))
        return img.resize((target_w, target_h), Image.LANCZOS)


def resize_for_platform(image_path: str, platform: str,
                        pad_mode: bool = False,
                        quality: int = 90) -> Optional[str]:
    """ปรับขนาดรูป → spec ของ platform → คืน path ใหม่ (temp)
    platform: facebook | facebook_square | line | tiktok | instagram
    """
    from PIL import Image

    spec = SPECS.get(platform)
    if not spec:
        logger.warning(f"Unknown platform: {platform}")
        return image_path

    try:
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")

        target_w, target_h = spec
        result = _smart_crop_resize(img, target_w, target_h, pad_mode=pad_mode)

        out = str(Path(tempfile.gettempdir()) / f"resized_{platform}_{int(time.time()*1000)}.jpg")
        result.save(out, "JPEG", quality=quality, optimize=True)
        logger.info(f"Resized for {platform}: {img.size} → {spec}")
        return out
    except Exception as e:
        logger.error(f"Resize failed for {platform}: {e}")
        return image_path  # คืนรูปเดิมถ้า resize ล้ม


def resize_for_facebook(image_path: str, square: bool = False) -> Optional[str]:
    """FB — แนวนอน 1200x630 หรือ จตุรัส 1080x1080"""
    return resize_for_platform(image_path, "facebook_square" if square else "facebook")


def resize_for_line(image_path: str) -> Optional[str]:
    """LINE — จตุรัส 1040x1040"""
    return resize_for_platform(image_path, "line")


def make_tiktok_slideshow(image_paths: list, seconds_per_image: float = 3,
                          fps: int = 30) -> Optional[str]:
    """สร้าง TikTok video 9:16 จากรูปหลายๆ ตัว (auto resize เป็น 1080x1920)"""
    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image

    if not image_paths:
        return None

    W, H = SPECS["tiktok"]
    out = str(Path(tempfile.gettempdir()) / f"tiktok_slide_{int(time.time()*1000)}.mp4")
    writer = imageio.get_writer(out, fps=fps, codec="libx264",
                                 output_params=["-pix_fmt", "yuv420p", "-crf", "23"])

    frames_per_img = int(fps * seconds_per_image)
    for path in image_paths[:8]:
        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            framed = _smart_crop_resize(img, W, H, pad_mode=True)  # pad_mode เพราะแนวตั้ง
            arr = np.array(framed)
            for _ in range(frames_per_img):
                writer.append_data(arr)
        except Exception as e:
            logger.warning(f"skip image {path}: {e}")

    writer.close()
    logger.info(f"TikTok slideshow: {out}")
    return out


def get_platform_dimensions(platform: str) -> Tuple[int, int]:
    """คืนขนาด (w, h) ของ platform"""
    return SPECS.get(platform, (1080, 1080))
