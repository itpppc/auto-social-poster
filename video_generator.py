# -*- coding: utf-8 -*-
"""
Video Generator — สร้าง MP4 จาก content สำหรับ Facebook Reel/Video Post
3 โหมด สลับไปอัตโนมัติทุกรอบ:
  1. Slideshow — 5 รูป AI + transition + text overlay (20 วินาที)
  2. Motion Reel — 1 รูป + Ken Burns (zoom/pan) + ข้อความเลื่อน (15 วินาที)
  3. Static — 1 รูป + slow zoom + CTA overlay (10 วินาที)
"""
import io, os, time, random, tempfile, logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class VideoGenerator:
    def __init__(self, gemini_api_key: str):
        from gemini_image_generator import GeminiImageGenerator
        self.img_gen = GeminiImageGenerator(gemini_api_key)

    # ──────────────────────────────────────────────────────
    # โหมด 1: SLIDESHOW (5 รูป + transition + BGM)
    # ──────────────────────────────────────────────────────
    def make_slideshow(self, topic: str, niche: str, content_text: str,
                        num_images: int = 5, seconds_per_image: float = 4,
                        size: tuple = (1280, 720)) -> Optional[str]:
        import imageio.v2 as imageio
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont

        W, H = size
        fps = 30
        frames_per_image = int(fps * seconds_per_image)
        trans_frames = 10  # transition fade frames

        # 1. Generate รูปหลายๆ ตัว
        logger.info(f"Slideshow: generating {num_images} images...")
        images = []
        prompt_base = self.img_gen._fallback_prompt(topic, niche)
        prompts = [
            prompt_base + ", wide angle establishing shot",
            prompt_base + ", close-up detail shot, macro lens",
            prompt_base + ", overhead aerial view",
            prompt_base + ", side profile shot, golden hour",
            prompt_base + ", dramatic lighting, hero shot",
        ][:num_images]

        for i, p in enumerate(prompts):
            path = self.img_gen.generate_image(p, width=W, height=H)
            if path:
                img = Image.open(path).convert("RGB").resize((W, H), Image.LANCZOS)
                images.append(self._add_text_overlay(img, topic if i == 0 else "", i + 1, len(prompts)))

        if len(images) < 2:
            logger.error("Not enough images for slideshow")
            return None

        # 2. รวมเป็น video พร้อม cross-fade
        out_path = Path(tempfile.gettempdir()) / f"slideshow_{int(time.time()*1000)}.mp4"
        writer = imageio.get_writer(str(out_path), fps=fps, codec="libx264",
                                     output_params=["-pix_fmt", "yuv420p", "-crf", "23"])

        for i, img in enumerate(images):
            arr = np.array(img)
            # hold
            for _ in range(frames_per_image - trans_frames):
                writer.append_data(arr)
            # crossfade to next
            if i < len(images) - 1:
                next_arr = np.array(images[i + 1])
                for f in range(trans_frames):
                    alpha = (f + 1) / (trans_frames + 1)
                    blend = (arr * (1 - alpha) + next_arr * alpha).astype(np.uint8)
                    writer.append_data(blend)

        writer.close()

        # 3. เพิ่ม end card (Logo + CTA)
        out2 = self._append_endcard(str(out_path), topic, fps=fps)
        return out2 or str(out_path)

    # ──────────────────────────────────────────────────────
    # โหมด 2: MOTION REEL (Ken Burns + animated text)
    # ──────────────────────────────────────────────────────
    def make_motion_reel(self, topic: str, niche: str, content_text: str,
                         duration_sec: int = 15, size: tuple = (1080, 1920)) -> Optional[str]:
        import imageio.v2 as imageio
        import numpy as np
        from PIL import Image

        W, H = size
        fps = 30
        total_frames = duration_sec * fps

        # 1. รูปคุณภาพสูงเพื่อ zoom/pan ได้
        prompt = self.img_gen._fallback_prompt(topic, niche)
        path = self.img_gen.generate_image(prompt, width=1920, height=1920)
        if not path:
            return None

        img = Image.open(path).convert("RGB")
        src_w, src_h = img.size

        out_path = Path(tempfile.gettempdir()) / f"reel_{int(time.time()*1000)}.mp4"
        writer = imageio.get_writer(str(out_path), fps=fps, codec="libx264",
                                     output_params=["-pix_fmt", "yuv420p", "-crf", "23"])

        # Ken Burns: zoom จาก 100% → 115%, pan ทแยง
        for f in range(total_frames):
            t = f / total_frames
            scale = 1.0 + 0.15 * t
            crop_w = int(src_w / scale)
            crop_h = int(src_h / scale)
            x = int((src_w - crop_w) * t)  # pan horizontal
            y = int((src_h - crop_h) * (1 - t))  # pan vertical
            crop = img.crop((x, y, x + crop_w, y + crop_h)).resize((W, H), Image.LANCZOS)

            # Animated text — slide in from bottom
            frame = self._add_animated_text(crop, topic, t, niche)
            writer.append_data(np.array(frame))

        writer.close()
        return str(out_path)

    # ──────────────────────────────────────────────────────
    # โหมด 3: STATIC (1 รูป + slow zoom + CTA)
    # ──────────────────────────────────────────────────────
    def make_static_video(self, topic: str, niche: str, content_text: str,
                           duration_sec: int = 10, size: tuple = (1280, 720)) -> Optional[str]:
        import imageio.v2 as imageio
        import numpy as np
        from PIL import Image

        W, H = size
        fps = 30
        total_frames = duration_sec * fps

        prompt = self.img_gen._fallback_prompt(topic, niche)
        path = self.img_gen.generate_image(prompt, width=1600, height=900)
        if not path:
            return None

        img = Image.open(path).convert("RGB")
        out_path = Path(tempfile.gettempdir()) / f"static_{int(time.time()*1000)}.mp4"
        writer = imageio.get_writer(str(out_path), fps=fps, codec="libx264",
                                     output_params=["-pix_fmt", "yuv420p", "-crf", "23"])

        # Slow zoom
        for f in range(total_frames):
            t = f / total_frames
            scale = 1.0 + 0.08 * t
            sw, sh = img.size
            cw, ch = int(sw / scale), int(sh / scale)
            x, y = (sw - cw) // 2, (sh - ch) // 2
            crop = img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.LANCZOS)
            frame = self._add_text_overlay(crop, topic, 0, 1, cta=t > 0.5)
            writer.append_data(np.array(frame))

        writer.close()
        return str(out_path)

    # ──────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────
    def _add_text_overlay(self, img, title: str, idx: int, total: int, cta: bool = False):
        from PIL import Image, ImageDraw, ImageFont
        img = img.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        W, H = img.size

        # Bottom gradient overlay
        gradient_h = int(H * 0.35)
        for y in range(gradient_h):
            alpha = int(180 * (y / gradient_h) ** 1.5)
            draw.rectangle([0, H - gradient_h + y, W, H - gradient_h + y + 1], fill=(0, 0, 0, alpha))

        if title:
            font_size = max(28, W // 28)
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", font_size)
            except:
                font = ImageFont.load_default()
            # Wrap text
            words = title.split()
            lines, cur = [], ""
            for w in words:
                test = (cur + " " + w).strip()
                if draw.textlength(test, font=font) > W * 0.85:
                    if cur: lines.append(cur)
                    cur = w
                else:
                    cur = test
            if cur: lines.append(cur)

            y = H - int(H * 0.18) - (font_size + 4) * len(lines)
            for ln in lines:
                draw.text((W // 2, y), ln, fill=(255, 255, 255, 255),
                          font=font, anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0, 200))
                y += font_size + 6

        if cta:
            try:
                cta_font = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", max(20, W // 40))
            except:
                cta_font = ImageFont.load_default()
            draw.text((W // 2, H - 30), "📩 LINE @itpppc · 📞 0909728573",
                      fill=(255, 220, 100, 255), font=cta_font, anchor="mb",
                      stroke_width=2, stroke_fill=(0, 0, 0, 255))

        # Top progress dots
        if total > 1:
            dot_y = 20
            for i in range(total):
                color = (255, 255, 255, 255) if i + 1 == idx else (255, 255, 255, 100)
                cx = W // 2 - (total * 12) // 2 + i * 12 + 6
                draw.ellipse([cx - 4, dot_y - 4, cx + 4, dot_y + 4], fill=color)

        return img

    def _add_animated_text(self, img, text: str, t: float, niche: str):
        from PIL import ImageDraw, ImageFont
        img = img.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        W, H = img.size

        # Bottom 40% gradient
        for y in range(int(H * 0.4)):
            alpha = int(220 * (y / (H * 0.4)) ** 1.5)
            draw.rectangle([0, H - int(H * 0.4) + y, W, H - int(H * 0.4) + y + 1], fill=(0, 0, 0, alpha))

        # Slide-in text
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", max(36, W // 22))
            cta_font = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", max(24, W // 30))
        except:
            font = ImageFont.load_default()
            cta_font = font

        # Slide animation
        slide_progress = min(1.0, t * 3)
        target_y = int(H * 0.7)
        y = int(H + (target_y - H) * slide_progress)

        if t < 0.5:
            shown = text
        else:
            shown = text + ""

        # Wrap
        words = shown.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=font) > W * 0.9:
                if cur: lines.append(cur)
                cur = w
            else:
                cur = test
        if cur: lines.append(cur)

        cy = y
        for ln in lines:
            draw.text((W // 2, cy), ln, fill=(255, 255, 255, 255),
                      font=font, anchor="mt", stroke_width=3, stroke_fill=(0, 0, 0, 220))
            cy += font.size + 8

        # CTA — fade in second half
        if t > 0.4:
            cta_alpha = int(min(255, (t - 0.4) * 500))
            draw.text((W // 2, H - 60), "📩 LINE @itpppc",
                      fill=(255, 220, 50, cta_alpha), font=cta_font, anchor="mb",
                      stroke_width=3, stroke_fill=(0, 0, 0, cta_alpha))

        return img

    def _append_endcard(self, video_path: str, topic: str, fps: int = 30) -> Optional[str]:
        """ต่อท้าย end card 2 วินาที — LINE/Tel/Web"""
        import imageio.v2 as imageio
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont

        try:
            reader = imageio.get_reader(video_path)
            first_frame = reader.get_data(0)
            H, W = first_frame.shape[:2]
            reader.close()

            # Create end card
            card = Image.new("RGB", (W, H), (15, 23, 42))
            draw = ImageDraw.Draw(card)

            try:
                title_font = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", max(40, W // 20))
                body_font = ImageFont.truetype("C:/Windows/Fonts/tahomabd.ttf", max(28, W // 30))
            except:
                title_font = ImageFont.load_default()
                body_font = title_font

            draw.text((W // 2, int(H * 0.3)), "TON AI Tech",
                      fill=(99, 102, 241), font=title_font, anchor="mm")
            draw.text((W // 2, int(H * 0.45)), "โซลูชัน IT ครบวงจร",
                      fill=(255, 255, 255), font=body_font, anchor="mm")
            draw.text((W // 2, int(H * 0.65)), "📩 LINE @itpppc",
                      fill=(255, 220, 100), font=body_font, anchor="mm")
            draw.text((W // 2, int(H * 0.75)), "📞 0909728573",
                      fill=(255, 220, 100), font=body_font, anchor="mm")

            # Append 2 sec
            out_path = video_path.replace(".mp4", "_final.mp4")
            writer = imageio.get_writer(out_path, fps=fps, codec="libx264",
                                         output_params=["-pix_fmt", "yuv420p", "-crf", "23"])
            reader = imageio.get_reader(video_path)
            for frame in reader:
                writer.append_data(frame)
            reader.close()
            arr = np.array(card)
            for _ in range(fps * 2):
                writer.append_data(arr)
            writer.close()
            return out_path
        except Exception as e:
            logger.warning(f"End card append failed: {e}")
            return None

    # ──────────────────────────────────────────────────────
    # Main API — สลับโหมด
    # ──────────────────────────────────────────────────────
    def generate_for_post(self, topic: str, niche: str, content_text: str = "",
                          mode: Optional[str] = None) -> Optional[str]:
        """mode: 'slideshow' | 'reel' | 'static' | None (random)"""
        if not mode:
            # สลับตามชั่วโมง: 07=slideshow, 12=reel, 18=static
            from datetime import datetime
            hr = datetime.now().hour
            mode = {7: "slideshow", 12: "reel", 18: "static"}.get(hr,
                   random.choice(["slideshow", "reel", "static"]))

        logger.info(f"Video mode: {mode}")
        if mode == "slideshow":
            return self.make_slideshow(topic, niche, content_text)
        elif mode == "reel":
            return self.make_motion_reel(topic, niche, content_text)
        else:
            return self.make_static_video(topic, niche, content_text)
