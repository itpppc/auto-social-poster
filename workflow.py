"""
Main Workflow — สร้าง content และโพสต์ลงทุก platform
+ Status tracker เขียน realtime ไปยัง current_status.json
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import Config
from content_generator import ContentGenerator, GeneratedContent
from facebook_poster import FacebookPoster
from line_poster import LinePoster
from tiktok_poster import TikTokPoster
import status_tracker as st

logger = logging.getLogger(__name__)


class PostResult:
    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        self.content_topic = ""
        self.results = []
        self.errors = []

    def to_dict(self) -> dict:
        return {
            "timestamp":     self.timestamp,
            "topic":         self.content_topic,
            "results":       self.results,
            "errors":        self.errors,
            "success_count": len(self.results),
            "error_count":   len(self.errors),
        }


class AutoPosterWorkflow:
    def __init__(self, config: Config):
        self.config    = config
        self.generator = ContentGenerator(config)

        self.fb     = FacebookPoster(config, generator=self.generator) if config.enable_facebook else None
        self.line   = LinePoster(config) if config.enable_line and config.line_channel_access_token else None
        self.tiktok = TikTokPoster(config) if config.enable_tiktok else None

        self.image_finder = None
        if config.pexels_api_key:
            from image_finder import ImageFinder
            self.image_finder = ImageFinder(config.pexels_api_key)

        # AI Image Generator (Pollinations.ai — ฟรี ไม่ต้อง key)
        self.ai_image = None
        self.ai_video = None
        if config.gemini_api_key:
            try:
                from gemini_image_generator import GeminiImageGenerator
                self.ai_image = GeminiImageGenerator(config.gemini_api_key)
                logger.info("AI Image Generator enabled (Pollinations.ai)")
            except Exception as e:
                logger.warning(f"AI image gen failed to init: {e}")
            try:
                from video_generator import VideoGenerator
                self.ai_video = VideoGenerator(config.gemini_api_key)
                logger.info("AI Video Generator enabled (3 modes)")
            except Exception as e:
                logger.warning(f"AI video gen failed to init: {e}")

        self.log_dir = Path("post_logs")
        self.log_dir.mkdir(exist_ok=True)

    # ──────────────────────────────────────────────────────
    # PREVIEW ONLY (generate content, don't post)
    # ──────────────────────────────────────────────────────
    def preview(self) -> dict:
        st.start_run("preview")
        content = self.generator.generate()
        st.set_topic(content.topic, content.source)

        # Facebook previews (per page)
        fb_previews = []
        if self.fb:
            for page in self.config.facebook_pages:
                page_niche = page.get("niche", self.config.content_niche)
                if page_niche != self.config.content_niche:
                    page_content = self.generator.generate(niche=page_niche)
                else:
                    page_content = content
                hashtags_str = " ".join(page_content.hashtags)
                fb_previews.append({
                    "page_id":   page["id"],
                    "page_name": page.get("niche", page["id"][-4:]),
                    "niche":     page_niche,
                    "text":      f"{page_content.facebook_post}\n\n{hashtags_str}",
                    "hashtags":  page_content.hashtags,
                    "image_url": "",
                })
        st.set_facebook_preview(fb_previews)

        # LINE preview
        if self.line:
            line_niche = self.config.line_content_niche or self.config.content_niche
            line_content = self.generator.generate(niche=line_niche) if line_niche != self.config.content_niche else content
            st.set_line_preview(line_content.line_message)

        # TikTok preview
        if self.tiktok:
            st.set_tiktok_preview(content.tiktok_script)

        st.set_stage("preview_ready")
        return st.get_status()

    # ──────────────────────────────────────────────────────
    # REAL RUN (generate + post)
    # ──────────────────────────────────────────────────────
    def run(
        self,
        custom_topic: Optional[str] = None,
        video_path:   Optional[str] = None,
        trigger:      str = "scheduled",
    ) -> PostResult:
        result = PostResult()
        st.start_run(trigger)

        try:
            logger.info("=== เริ่มสร้าง content ===")
            st.set_stage("generating")
            content = self.generator.generate(custom_topic)
            result.content_topic = content.topic
            st.set_topic(content.topic, content.source)
            logger.info(f"ที่มา: {content.source}")
            logger.info(f"หัวข้อ: {content.topic}")

            # ─── FACEBOOK (per-page) ─────────────────────
            if self.fb and self.config.enable_facebook:
                st.set_stage("facebook")
                self._post_facebook_with_tracking(content, result)

            # ─── LINE ────────────────────────────────────
            if self.line:
                st.set_stage("line")
                line_niche = self.config.line_content_niche or self.config.content_niche
                if line_niche != self.config.content_niche:
                    logger.info(f"LINE niche: {line_niche}")
                    line_content = self.generator.generate(custom_topic, niche=line_niche)
                else:
                    line_content = content
                st.set_line_preview(line_content.line_message)

                # ลองสร้าง media สำหรับ LINE
                line_media_url = None
                line_media_type = None
                line_preview_url = None
                try:
                    from media_uploader import upload_media
                    from datetime import datetime
                    hr = datetime.now().hour

                    # ★ PRIORITY 1: รูป user (resize เป็น LINE spec 1040x1040)
                    try:
                        from local_image_pool import get_local_image
                        from image_resizer import resize_for_line
                        line_local = get_local_image(niche=line_niche)
                        if line_local:
                            resized = resize_for_line(line_local)
                            line_media_url = upload_media(resized)
                            line_media_type = "image"
                            logger.info(f"LINE: ใช้รูป user → {line_local}")
                    except Exception as e:
                        logger.warning(f"LINE local image error: {e}")

                    use_video_line = (not line_media_url) and self.ai_video and hr == 18

                    if use_video_line:
                        vid_path = self.ai_video.generate_for_post(
                            topic=line_content.topic, niche=line_niche,
                            content_text=line_content.line_message, mode="reel",
                        )
                        if vid_path:
                            # video → upload + ใช้ first frame เป็น preview
                            line_media_url = upload_media(vid_path)
                            # preview = upload first frame screenshot
                            preview_img = self._extract_video_thumbnail(vid_path)
                            if preview_img:
                                line_preview_url = upload_media(preview_img)
                            line_media_type = "video"

                    if not line_media_url and self.ai_image:
                        # ใช้ facebook_post ถ้ามี เพราะเนื้อหายาวกว่า → image กว้างกว่า
                        img_source = (line_content.facebook_post or line_content.line_message)
                        img_path = self.ai_image.generate_for_post(
                            topic=line_content.topic, niche=line_niche,
                            content_summary=img_source,
                        )
                        if img_path:
                            line_media_url = upload_media(img_path)
                            line_media_type = "image"
                except Exception as e:
                    logger.warning(f"LINE media gen failed: {e}")

                try:
                    line_text = (f"{line_content.line_message}\n\n"
                                  + " ".join(line_content.hashtags or []))
                    if line_media_url:
                        data = self.line.broadcast_with_media(
                            text=line_text,
                            media_url=line_media_url,
                            media_type=line_media_type,
                            preview_url=line_preview_url,
                        )
                    else:
                        data = self.line.broadcast_flex(line_content)
                    result.results.append(data)
                    st.update_line_status("success")
                    logger.info(f"[OK] LINE Broadcast — {line_media_type or 'flex'}")
                except Exception as e:
                    err = str(e)
                    result.errors.append(f"LINE: {err}")
                    st.update_line_status("failed", err)
                    logger.error(f"[ERROR] LINE: {err}")

            # ─── TIKTOK ──────────────────────────────────
            if self.tiktok and self.config.enable_tiktok:
                st.set_stage("tiktok")
                st.set_tiktok_preview(content.tiktok_script)
                try:
                    tt_video = None
                    # 1) ลอง AI video ก่อน (Reel 9:16 ใช้ได้ทุกรอบ)
                    if self.ai_video:
                        try:
                            tt_video = self.ai_video.generate_for_post(
                                topic=content.topic, niche=self.config.content_niche,
                                content_text=content.tiktok_script or content.topic, mode="reel",
                            )
                        except Exception as e:
                            logger.warning(f"TikTok AI video failed: {e}")

                    if tt_video:
                        data = self.tiktok.upload_video(content, tt_video)
                    elif video_path:
                        data = self.tiktok.upload_video(content, video_path)
                    elif self.image_finder:
                        query = self.generator.get_image_query(content.topic, self.config.content_niche)
                        image_urls = self.image_finder.search_multiple(query, count=5, orientation="portrait")
                        if image_urls:
                            data = self.tiktok.post_photo_mode(content, image_urls)
                        else:
                            raise Exception("ไม่พบ video/รูป")
                    else:
                        raise Exception("ไม่มี video หรือ image_finder")
                    result.results.append(data)
                    st.update_tiktok_status("success")
                    logger.info("[OK] TikTok — สำเร็จ")
                except Exception as e:
                    err = str(e)
                    result.errors.append(f"TikTok: {err}")
                    st.update_tiktok_status("failed", err)
                    logger.error(f"[ERROR] TikTok: {err}")

            self._save_log(result, content)
            self._print_summary(result)

        finally:
            st.finish_run()

        return result

    # ──────────────────────────────────────────────────────
    def _post_facebook_with_tracking(self, content, result: PostResult):
        """Post FB ทีละ page + track status แต่ละ page"""
        if not self.fb.pages:
            return

        # Generate previews ทุก page ล่วงหน้า
        fb_previews = []
        page_contents = {}
        for page in self.fb.pages:
            page_id    = page["id"]
            page_niche = page.get("niche", self.config.content_niche)

            if page_niche != self.config.content_niche:
                pc = self.generator.generate(niche=page_niche)
            else:
                pc = content
            page_contents[page_id] = pc

            hashtags_str = " ".join(pc.hashtags)
            fb_previews.append({
                "page_id":   page_id,
                "page_name": page_niche,
                "niche":     page_niche,
                "text":      f"{pc.facebook_post}\n\n{hashtags_str}",
                "hashtags":  pc.hashtags,
                "image_url": "",
            })
        st.set_facebook_preview(fb_previews)

        # โพสต์ทีละ page
        results = []
        errors  = []
        for page in self.fb.pages:
            page_id    = page["id"]
            token      = page["token"]
            page_niche = page.get("niche", self.config.content_niche)
            pc         = page_contents[page_id]

            try:
                hashtags_str = " ".join(pc.hashtags)
                full_text    = f"{pc.facebook_post}\n\n{hashtags_str}"

                from datetime import datetime
                hr = datetime.now().hour

                ai_video_path = None
                ai_image_path = None

                # ★ PRIORITY 1: รูปที่ user เตรียมไว้เอง (my_images/)
                local_img = None
                try:
                    from local_image_pool import get_local_image
                    local_img = get_local_image(page_id=page_id, niche=page_niche)
                    if local_img:
                        logger.info(f"Page {page_id[-4:]}: ใช้รูปของ user → {local_img}")
                except Exception as e:
                    logger.warning(f"local image pool error: {e}")

                # PRIORITY 2: ถ้าไม่มีรูป user → AI video (รอบ 12/18) หรือ AI image
                if not local_img:
                    use_video = self.ai_video and hr in (12, 18)
                    if use_video:
                        try:
                            mode = "reel" if hr == 12 else "static"
                            ai_video_path = self.ai_video.generate_for_post(
                                topic=pc.topic, niche=page_niche,
                                content_text=pc.facebook_post, mode=mode,
                            )
                        except Exception as e:
                            logger.warning(f"AI video gen failed: {e}")

                    if not ai_video_path and self.ai_image:
                        try:
                            ai_image_path = self.ai_image.generate_for_post(
                                topic=pc.topic, niche=page_niche,
                                content_summary=pc.facebook_post,
                            )
                        except Exception as e:
                            logger.warning(f"AI image gen failed for page {page_id[-4:]}: {e}")

                # PRIORITY 3: Pexels stock
                image_url = None
                if not local_img and not ai_video_path and not ai_image_path and self.fb.image_finder and self.generator:
                    query = self.generator.get_image_query(pc.topic, page_niche)
                    image_url = self.fb.image_finder.search(query)

                # Post — ลำดับ: local → video → AI image → Pexels → text
                if local_img:
                    # Auto-resize รูป user → FB spec (1200x630) ก่อนโพส
                    try:
                        from image_resizer import resize_for_facebook
                        fb_img = resize_for_facebook(local_img)
                    except Exception as e:
                        logger.warning(f"FB resize failed, use original: {e}")
                        fb_img = local_img
                    post_id = self._fb_post_local_image(page_id, token, full_text, fb_img)
                    has_image, has_video = True, False
                elif ai_video_path:
                    post_id = self._fb_post_video(page_id, token, full_text, ai_video_path)
                    has_image, has_video = False, True
                elif ai_image_path:
                    post_id = self._fb_post_local_image(page_id, token, full_text, ai_image_path)
                    has_image, has_video = True, False
                elif image_url:
                    post_id = self.fb._post_with_photo(page_id, token, full_text, image_url)
                    has_image, has_video = True, False
                else:
                    post_id = self.fb._post_feed(page_id, token, full_text)
                    has_image, has_video = False, False

                results.append({"page_id": page_id, "post_id": post_id, "niche": page_niche,
                                "has_image": has_image, "has_video": has_video,
                                "ai_image": ai_image_path is not None, "ai_video": ai_video_path is not None,
                                "user_image": local_img is not None})
                st.update_facebook_status(page_id, "success")
            except Exception as e:
                err = str(e)
                errors.append(err)
                st.update_facebook_status(page_id, "failed", err)
                logger.error(f"Facebook page {page_id} error: {err}")

        if results:
            result.results.append({"platform": "facebook", "pages": results, "errors": errors})
        if errors and not results:
            result.errors.append(f"Facebook: {errors[0]}")

    def _fb_post_local_image(self, page_id: str, token: str, caption: str, image_path: str) -> str:
        """อัปโหลดรูปท้องถิ่น (AI generated) → Facebook Page"""
        import requests
        with open(image_path, "rb") as f:
            r = requests.post(
                f"https://graph.facebook.com/v21.0/{page_id}/photos",
                files={"source": f},
                data={"caption": caption, "access_token": token}, timeout=60,
            )
        j = r.json()
        if "error" in j:
            raise Exception(j["error"].get("message", str(j["error"])))
        return j.get("post_id") or j.get("id", "")

    def _extract_video_thumbnail(self, video_path: str) -> str:
        """ดึง frame แรกของ video เป็นรูป JPG → คืน path"""
        try:
            import imageio.v2 as imageio
            from PIL import Image
            import tempfile, time
            reader = imageio.get_reader(video_path)
            frame = reader.get_data(0)
            reader.close()
            img = Image.fromarray(frame)
            if img.mode != "RGB": img = img.convert("RGB")
            out = str(Path(tempfile.gettempdir()) / f"thumb_{int(time.time()*1000)}.jpg")
            img.save(out, "JPEG", quality=85)
            return out
        except Exception as e:
            logger.warning(f"thumbnail extract failed: {e}")
            return None

    def _fb_post_video(self, page_id: str, token: str, description: str, video_path: str) -> str:
        """อัปโหลด video → Facebook Page"""
        import requests
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://graph-video.facebook.com/v21.0/{page_id}/videos",
                files={"source": f},
                data={"description": description, "access_token": token}, timeout=300,
            )
        j = r.json()
        if "error" in j:
            raise Exception(j["error"].get("message", str(j["error"])))
        return j.get("id", "")

    # ──────────────────────────────────────────────────────
    def _post_to_platform(self, platform: str, post_fn, result: PostResult):
        """legacy helper (ยังใช้กับ paths อื่นได้)"""
        try:
            logger.info(f"กำลังโพสต์ไปยัง {platform}...")
            data = post_fn()
            result.results.append(data)
            logger.info(f"[OK] {platform} — สำเร็จ")
        except Exception as e:
            error_msg = f"{platform}: {str(e)}"
            result.errors.append(error_msg)
            logger.error(f"[ERROR] {error_msg}")

    def _save_log(self, result: PostResult, content: GeneratedContent):
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"post_{date_str}.json"
        log_data = result.to_dict()
        log_data["content"] = {
            "topic":          content.topic,
            "source":         content.source,
            "facebook_post":  content.facebook_post,
            "line_message":   content.line_message,
            "tiktok_script":  content.tiktok_script,
            "hashtags":       content.hashtags,
            "call_to_action": content.call_to_action,
        }
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        logger.info(f"บันทึก log: {log_file.name}")

        # Sync to Firestore (silent fail if not configured)
        try:
            import firestore_sync
            firestore_sync.sync_post_log(log_data)
        except Exception as e:
            logger.warning(f"Firestore sync skipped: {e}")

    def _print_summary(self, result: PostResult):
        print("\n" + "=" * 50)
        print(f"สรุปผล — {result.timestamp}")
        print(f"สำเร็จ: {len(result.results)} | ล้มเหลว: {len(result.errors)}")
        for err in result.errors:
            print(f"  - {err}")
        print("=" * 50 + "\n")
