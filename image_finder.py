"""
Image Finder — ค้นหารูปจาก Pexels (ฟรี)
สมัคร API Key ฟรี: https://www.pexels.com/api/
"""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

PEXELS_BASE = "https://api.pexels.com/v1"


class ImageFinder:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": api_key}

    def search(self, query: str) -> Optional[str]:
        urls = self.search_multiple(query, count=1, orientation="landscape")
        return urls[0] if urls else None

    def search_multiple(self, query: str, count: int = 5, orientation: str = "portrait") -> list[str]:
        try:
            r = requests.get(
                f"{PEXELS_BASE}/search",
                headers=self.headers,
                params={"query": query, "per_page": min(count, 10), "orientation": orientation},
                timeout=10,
            )
            photos = r.json().get("photos", [])
            urls = [p["src"]["large"] for p in photos]
            logger.info(f"Pexels: {len(urls)} images for '{query}'")
            return urls
        except Exception as e:
            logger.warning(f"Pexels search error: {e}")
        return []
