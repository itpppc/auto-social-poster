"""
Facebook Page Auto Poster
ใช้ Facebook Graph API โพสต์ลง Page อัตโนมัติ — รองรับหลาย Page แต่ละ Page มี niche ของตัวเอง
รองรับโพสต์พร้อมรูปภาพจาก Pexels (ถ้าตั้งค่า PEXELS_API_KEY)
"""
import requests
import logging
from typing import Optional
from content_generator import GeneratedContent, ContentGenerator
from config import Config

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class FacebookPoster:
    def __init__(self, config: Config, generator: Optional[ContentGenerator] = None):
        self.config = config
        self.pages = config.facebook_pages
        self.generator = generator

        self.image_finder = None
        if config.pexels_api_key:
            from image_finder import ImageFinder
            self.image_finder = ImageFinder(config.pexels_api_key)
            logger.info("Image finder enabled (Pexels)")

    def post(self, content: Optional[GeneratedContent] = None) -> dict:
        if not self.pages:
            raise ValueError("ต้องตั้งค่า FACEBOOK_PAGE_ID และ FACEBOOK_ACCESS_TOKEN")

        results = []
        errors = []
        for page in self.pages:
            page_id = page["id"]
            token = page["token"]
            page_niche = page.get("niche", self.config.content_niche)

            if self.generator and page_niche != self.config.content_niche:
                page_content = self.generator.generate(niche=page_niche)
                logger.info(f"Generated custom content for page {page_id} niche: {page_niche}")
            elif content is not None:
                page_content = content
            elif self.generator:
                page_content = self.generator.generate(niche=page_niche)
            else:
                raise ValueError("ต้องส่ง content หรือ generator")

            try:
                hashtags_str = " ".join(page_content.hashtags)
                full_text = f"{page_content.facebook_post}\n\n{hashtags_str}"

                # หารูปภาพถ้ามี Pexels API key
                image_url = None
                if self.image_finder and self.generator:
                    query = self.generator.get_image_query(page_content.topic, page_niche)
                    logger.info(f"Image search query: {query}")
                    image_url = self.image_finder.search(query)

                if image_url:
                    post_id = self._post_with_photo(page_id, token, full_text, image_url)
                else:
                    post_id = self._post_feed(page_id, token, full_text)

                logger.info(f"Facebook page {page_id} posted: {post_id}")
                results.append({"page_id": page_id, "post_id": post_id, "niche": page_niche, "has_image": image_url is not None})
            except Exception as e:
                logger.error(f"Facebook page {page_id} error: {e}")
                errors.append(str(e))

        if errors and not results:
            raise Exception(f"Facebook post failed: {errors[0]}")

        return {"platform": "facebook", "pages": results, "errors": errors, "status": "success"}

    def _post_feed(self, page_id: str, token: str, text: str) -> str:
        url = f"{GRAPH_API_BASE}/{page_id}/feed"
        r = requests.post(url, data={"message": text, "access_token": token}, timeout=30)
        result = r.json()
        if "error" in result:
            raise Exception(result["error"]["message"])
        return result.get("id", "")

    def _post_with_photo(self, page_id: str, token: str, caption: str, image_url: str) -> str:
        url = f"{GRAPH_API_BASE}/{page_id}/photos"
        r = requests.post(url, data={"url": image_url, "caption": caption, "access_token": token}, timeout=60)
        result = r.json()
        if "error" in result:
            logger.warning(f"Photo post failed ({result['error']['message']}), falling back to text post")
            return self._post_feed(page_id, token, caption)
        return result.get("post_id") or result.get("id", "")

    def post_with_image(self, content: GeneratedContent, image_path: str) -> dict:
        """โพสต์พร้อมรูปภาพ"""
        url = f"{GRAPH_API_BASE}/{self.page_id}/photos"
        hashtags_str = " ".join(content.hashtags)
        caption = f"{content.facebook_post}\n\n{hashtags_str}"

        with open(image_path, "rb") as img_file:
            payload = {
                "caption": caption,
                "access_token": self.token,
            }
            files = {"source": img_file}
            response = requests.post(url, data=payload, files=files, timeout=60)

        result = response.json()
        if "error" in result:
            raise Exception(f"Facebook photo post failed: {result['error']['message']}")

        logger.info(f"Facebook photo posted: {result.get('post_id', '')}")
        return {"platform": "facebook", "post_id": result.get("post_id"), "status": "success"}

    def get_page_insights(self) -> dict:
        """ดู engagement stats ของ Page"""
        url = f"{GRAPH_API_BASE}/{self.page_id}/insights"
        params = {
            "metric": "page_post_engagements,page_impressions,page_fans",
            "period": "day",
            "access_token": self.token,
        }
        response = requests.get(url, params=params, timeout=30)
        return response.json()
