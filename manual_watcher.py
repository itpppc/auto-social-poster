# -*- coding: utf-8 -*-
"""
Manual Post Watcher — รับคำสั่งโพสต์จาก dashboard (Firebase RTDB queue)
→ ประมวลผล → โพสต์ FB/LINE/TikTok → อัปเดต status กลับ
"""
import base64
import logging
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _decode_image(b64_data: str) -> str:
    """แปลง base64 data URL → ไฟล์รูปใน temp folder → คืน path"""
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    img_bytes = base64.b64decode(b64_data)
    fname = f"manual_{int(time.time()*1000)}.jpg"
    path = Path(tempfile.gettempdir()) / fname
    path.write_bytes(img_bytes)
    return str(path)


def _generate_ai_content(generator, topic: str, niche: str):
    """ใช้ AI สร้างเนื้อหาเต็มจากหัวข้อ"""
    return generator.generate(custom_topic=topic, niche=niche)


def process_manual_post(post_id: str, data: dict, config, generator):
    """ประมวลผลคำสั่ง manual post 1 รายการ"""
    import firestore_sync as fs
    from facebook_poster import FacebookPoster
    from line_poster import LinePoster
    from tiktok_poster import TikTokPoster

    db = fs._db
    if db is None:
        logger.error("Manual: Firebase not initialized")
        return

    queue_ref = db.reference(f"manual_queue/{post_id}")

    try:
        queue_ref.update({"status": "processing", "started_at": datetime.now().isoformat()})

        topic        = data.get("topic", "").strip()
        custom_text  = data.get("content", "").strip()
        image_b64    = data.get("image_b64", "")
        platforms    = data.get("platforms", [])

        logger.info(f"[MANUAL] Processing: {topic[:60]}")
        logger.info(f"[MANUAL] Platforms: {platforms}")

        # Save image to temp file if provided
        image_path = None
        if image_b64:
            try:
                image_path = _decode_image(image_b64)
                logger.info(f"[MANUAL] Image saved: {image_path}")
            except Exception as e:
                logger.warning(f"[MANUAL] Image decode failed: {e}")

        results = []
        errors  = []
        logged_pages = []

        # ─── Facebook posts ───
        fb_targets = [p[3:] for p in platforms if p.startswith("fb_")]
        if fb_targets:
            fb_poster = FacebookPoster(config, generator=generator)
            all_fb_pages = {p["id"]: p for p in config.facebook_pages}

            for fb_page_id in fb_targets:
                page = all_fb_pages.get(fb_page_id)
                if not page:
                    errors.append(f"FB page {fb_page_id} not configured")
                    continue
                niche = page.get("niche", config.content_niche)

                # Build content
                if custom_text:
                    # User provided full text — use as-is
                    text = custom_text
                    hashtags = []
                    pc = None
                else:
                    pc = _generate_ai_content(generator, topic, niche)
                    text = f"{pc.facebook_post}\n\n{' '.join(pc.hashtags)}"

                # ถ้าไม่ได้แนบรูปมา → AI gen รูปให้
                use_image = image_path
                if not use_image:
                    try:
                        from gemini_image_generator import GeminiImageGenerator
                        ai_gen = GeminiImageGenerator(config.gemini_api_key)
                        summary = (custom_text[:200] if custom_text else
                                   (pc.facebook_post[:200] if pc else ""))
                        use_image = ai_gen.generate_for_post(topic=topic, niche=niche,
                                                              content_summary=summary)
                        if use_image:
                            logger.info(f"[MANUAL] AI image generated: {use_image}")
                    except Exception as e:
                        logger.warning(f"[MANUAL] AI image gen failed: {e}")

                try:
                    if use_image:
                        # Upload local image (user-supplied OR AI-generated)
                        post_id_fb = _fb_post_with_local_image(
                            fb_page_id, page["token"], text, use_image
                        )
                    else:
                        post_id_fb = fb_poster._post_feed(fb_page_id, page["token"], text)
                    logged_pages.append({
                        "page_id": fb_page_id, "post_id": post_id_fb,
                        "niche": niche, "has_image": bool(use_image),
                        "ai_image": bool(use_image and use_image != image_path),
                    })
                    logger.info(f"[MANUAL] FB {fb_page_id[-4:]} OK: {post_id_fb}")
                except Exception as e:
                    errors.append(f"FB {fb_page_id[-4:]}: {e}")
                    logger.error(f"[MANUAL] FB {fb_page_id[-4:]} failed: {e}")

            if logged_pages:
                results.append({"platform": "facebook", "pages": logged_pages})

        # ─── LINE Broadcast ───
        if "line" in platforms:
            try:
                line_poster = LinePoster(config)
                if custom_text:
                    # Direct text broadcast
                    line_poster.broadcast_text(custom_text)
                    results.append({"platform": "line", "status": "success"})
                else:
                    line_niche = config.line_content_niche or config.content_niche
                    pc = _generate_ai_content(generator, topic, line_niche)
                    line_poster.broadcast_flex(pc)
                    results.append({"platform": "line_flex", "status": "success"})
                logger.info(f"[MANUAL] LINE OK")
            except Exception as e:
                errors.append(f"LINE: {e}")
                logger.error(f"[MANUAL] LINE failed: {e}")

        # ─── TikTok ───
        if "tiktok" in platforms and config.enable_tiktok:
            try:
                tt = TikTokPoster(config)
                if image_path:
                    # Use the uploaded image as the only frame (will be wrapped as slideshow)
                    # Need to make it a list of URLs or local paths
                    # We have local file — tiktok_poster expects URLs for photo_mode
                    # For now: skip if only local image
                    errors.append("TikTok: ต้องใช้รูปจาก URL หรือ video (skip manual image)")
                else:
                    # Generate AI tiktok content + use Pexels
                    pc = _generate_ai_content(generator, topic, config.content_niche)
                    from image_finder import ImageFinder
                    if config.pexels_api_key:
                        finder = ImageFinder(config.pexels_api_key)
                        query = generator.get_image_query(topic, config.content_niche)
                        urls = finder.search_multiple(query, count=5, orientation="portrait")
                        if urls:
                            r = tt.post_photo_mode(pc, urls)
                            results.append(r)
                            logger.info(f"[MANUAL] TikTok OK")
                        else:
                            errors.append("TikTok: ไม่พบรูป Pexels")
                    else:
                        errors.append("TikTok: ต้องการ PEXELS_API_KEY")
            except Exception as e:
                errors.append(f"TikTok: {e}")
                logger.error(f"[MANUAL] TikTok failed: {e}")

        # ─── Save log ───
        log_data = {
            "timestamp":     datetime.now().isoformat(),
            "topic":         f"[Manual] {topic}",
            "results":       results,
            "errors":        errors,
            "success_count": len(results),
            "error_count":   len(errors),
            "content": {
                "topic":         topic,
                "source":        "Manual Web Composer",
                "facebook_post": custom_text or (pc.facebook_post if 'pc' in dir() and pc else ""),
                "line_message":  custom_text or "",
                "tiktok_script": "",
                "hashtags":      [],
                "call_to_action": "",
            },
        }

        # Save to local log file
        from pathlib import Path
        import json
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(__file__).parent / "post_logs" / f"post_{date_str}_manual.json"
        log_path.parent.mkdir(exist_ok=True)
        log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Sync to Firestore (post history)
        fs.sync_post_log(log_data)

        # Update queue entry
        status = "completed" if results and not errors else ("partial" if results else "failed")
        queue_ref.update({
            "status":       status,
            "finished_at":  datetime.now().isoformat(),
            "results_summary": {
                "success_count": len(results),
                "error_count":   len(errors),
                "errors":        errors[:5],
            },
        })
        logger.info(f"[MANUAL] Done — {status}, {len(results)} ok, {len(errors)} err")

        # Cleanup
        if image_path and Path(image_path).exists():
            try: Path(image_path).unlink()
            except: pass

    except Exception as e:
        logger.exception(f"[MANUAL] Fatal error processing {post_id}: {e}")
        try:
            queue_ref.update({"status": "failed", "error": str(e)[:500]})
        except: pass


def _fb_post_with_local_image(page_id: str, token: str, caption: str, image_path: str) -> str:
    """อัปโหลดรูปท้องถิ่น → Facebook Page"""
    import requests
    url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
    with open(image_path, "rb") as f:
        files = {"source": f}
        data = {"caption": caption, "access_token": token}
        r = requests.post(url, files=files, data=data, timeout=60)
    result = r.json()
    if "error" in result:
        raise Exception(result["error"].get("message", str(result["error"])))
    return result.get("post_id") or result.get("id", "")


def watch_manual_queue(config, generator):
    """Polling watcher — เช็ค manual_queue ทุก N วินาที"""
    import firestore_sync as fs

    if not fs._init():
        logger.warning("Manual watcher: Firebase ไม่พร้อม → ข้าม")
        return

    db = fs._db
    queue_ref = db.reference("manual_queue")
    seen = set()
    logger.info("Manual watcher: เริ่มทำงาน (poll ทุก 3 วินาที)")

    while True:
        try:
            data = queue_ref.get() or {}
            for post_id, item in data.items():
                if not isinstance(item, dict): continue
                if item.get("status") == "pending" and post_id not in seen:
                    seen.add(post_id)
                    logger.info(f"Manual: พบคำสั่งใหม่ {post_id}")
                    process_manual_post(post_id, item, config, generator)
        except Exception as e:
            logger.error(f"Manual watcher loop error: {e}")
        time.sleep(3)


def start_in_background(config, generator):
    """รัน watcher ใน daemon thread"""
    t = threading.Thread(
        target=watch_manual_queue,
        args=(config, generator),
        daemon=True,
        name="ManualWatcher",
    )
    t.start()
    return t
