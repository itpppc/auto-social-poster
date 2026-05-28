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
                try:
                    data = self.line.broadcast_flex(line_content)
                    result.results.append(data)
                    st.update_line_status("success")
                    logger.info("[OK] LINE Broadcast — สำเร็จ")
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
                    if video_path:
                        data = self.tiktok.upload_video(content, video_path)
                    elif self.image_finder:
                        query = self.generator.get_image_query(content.topic, self.config.content_niche)
                        image_urls = self.image_finder.search_multiple(query, count=5, orientation="portrait")
                        if image_urls:
                            data = self.tiktok.post_photo_mode(content, image_urls)
                        else:
                            raise Exception("ไม่พบรูป Pexels")
                    else:
                        raise Exception("ไม่มี image_finder")
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

                image_url = None
                if self.fb.image_finder and self.generator:
                    query = self.generator.get_image_query(pc.topic, page_niche)
                    image_url = self.fb.image_finder.search(query)

                if image_url:
                    post_id = self.fb._post_with_photo(page_id, token, full_text, image_url)
                else:
                    post_id = self.fb._post_feed(page_id, token, full_text)

                results.append({"page_id": page_id, "post_id": post_id, "niche": page_niche, "has_image": image_url is not None})
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
