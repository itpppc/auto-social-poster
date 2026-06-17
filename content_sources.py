"""
Content Sources — ดึง topic ideas จากแหล่งจริง ฟรีทั้งหมด

แหล่งข้อมูล:
  1. Google Trends Thailand   — ค้นหาอะไรมากที่สุดวันนี้
  2. RSS ข่าวไทย              — หัวข้อข่าวล่าสุด (Sanook, Kapook, Thairath)
  3. ปฏิทินไทย               — เทศกาล วันหยุด วันสำคัญ
  4. Evergreen topics         — หัวข้อคลาสสิคที่ยังดีเสมอ (fallback)
"""
import random
import datetime
import feedparser
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TopicIdea:
    title: str          # หัวข้อที่จะส่งให้ AI สร้าง content
    source: str         # ที่มา เช่น "Google Trends", "Sanook", "Calendar"
    keywords: list[str] # คำสำคัญเพิ่มเติม


# ===== RSS FEEDS ที่ verified ว่าทำงานได้ =====
RSS_FEEDS = {
    "The Standard":   "https://thestandard.co/feed/",
    "Positioning Mag":"https://positioningmag.com/feed",
    "The Matter":     "https://thematter.co/feed",
    "Marketeer":      "https://marketeeronline.co/feed",
    "Blognone":       "https://www.blognone.com/node/feed",
}

# RSS ตาม niche (ใช้ก่อน feeds ทั่วไป)
NICHE_RSS = {
    "การเงิน":    [
        "https://positioningmag.com/feed",
        "https://marketeeronline.co/feed",
    ],
    "สุขภาพ":    [
        "https://thestandard.co/feed/",
        "https://thematter.co/feed",
    ],
    "เทคโนโลยี": [
        "https://www.blognone.com/node/feed",
        "https://thestandard.co/feed/",
    ],
    "ท่องเที่ยว": [
        "https://thestandard.co/feed/",
        "https://positioningmag.com/feed",
    ],
    "ความงาม":   [
        "https://positioningmag.com/feed",
        "https://marketeeronline.co/feed",
    ],
}

# ===== ปฏิทินไทย — วันสำคัญ/เทศกาล =====
THAI_CALENDAR = {
    (1, 1):   "ปีใหม่",
    (2, 14):  "วาเลนไทน์",
    (4, 6):   "วันจักรี",
    (4, 13):  "สงกรานต์",
    (4, 14):  "สงกรานต์",
    (4, 15):  "สงกรานต์",
    (5, 1):   "วันแรงงาน",
    (5, 4):   "วันฉัตรมงคล",
    (6, 3):   "วันเฉลิมพระชนมพรรษา ราชินี",
    (7, 28):  "วันเฉลิมพระชนมพรรษา ร.10",
    (8, 12):  "วันแม่แห่งชาติ",
    (10, 13): "วันคล้ายวันสวรรคต ร.9",
    (10, 23): "วันปิยมหาราช",
    (12, 5):  "วันพ่อแห่งชาติ",
    (12, 31): "วันสิ้นปี",
}

# ===== EVERGREEN TOPICS ตาม niche (fallback) =====
EVERGREEN = {
    "การเงินและการลงทุน": [
        "วิธีเริ่มต้นลงทุนด้วยเงิน 1,000 บาท",
        "ความแตกต่างระหว่าง กองทุนรวม vs หุ้น",
        "วิธีออมเงินให้ได้ 10% ของรายได้ทุกเดือน",
        "DCA คืออะไร ทำไมคนรวยชอบใช้",
        "ภาษีที่มือใหม่ลงทุนต้องรู้",
        "5 ข้อผิดพลาดที่คนเริ่มลงทุนมักทำ",
        "กองทุน SSF vs RMF ต่างกันอย่างไร",
        "เงินเฟ้อกินเงินออมคุณอยู่ทุกวัน วิธีแก้คือ?",
    ],
    "สุขภาพและการออกกำลังกาย": [
        "ออกกำลังกาย 20 นาทีต่อวัน ได้ผลจริงไหม",
        "อาหารที่ควรกินก่อนและหลังออกกำลังกาย",
        "วิธีนอนหลับให้ดีขึ้นโดยไม่ต้องใช้ยา",
        "ดื่มน้ำวันละเท่าไหร่ถึงพอ",
        "5 ท่าออกกำลังกายในบ้านที่ไม่ต้องใช้อุปกรณ์",
    ],
    "เทคโนโลยีและ AI": [
        "AI จะมาแทนงานคุณไหม และควรเตรียมตัวอย่างไร",
        "10 เครื่องมือ AI ฟรีที่ใช้ในชีวิตประจำวันได้เลย",
        "ChatGPT vs Claude ใช้อะไรดีกว่ากัน",
        "วิธีใช้ AI เพิ่มประสิทธิภาพการทำงาน",
        "Prompt Engineering คืออะไร ทำไมต้องรู้",
    ],
    "ท่องเที่ยวไทย": [
        "10 ที่เที่ยวไทยที่ยังไม่ดังแต่สวยมาก",
        "งบท่องเที่ยวต่างจังหวัด 2 วัน 1 คืน 1,500 บาท",
        "เที่ยวทะเลไทยช่วงไหนดีที่สุด",
        "ของกินเที่ยวเหนือที่ต้องลอง",
        "วิธีหาโรงแรมถูกดีในไทย",
    ],
    "ความงามและสกินแคร์": [
        "Skincare routine เช้า-เย็น สำหรับมือใหม่",
        "SPF คืออะไร ทำไมต้องทากันแดดทุกวัน",
        "วิธีเลือกมอยส์เจอร์ไรเซอร์ให้เหมาะกับผิว",
        "ส่วนผสมในครีมที่ควรหลีกเลี่ยง",
        "Double cleansing คืออะไร จำเป็นไหม",
    ],
}


class ContentSources:
    def __init__(self, niche: str):
        self.niche = niche

    def get_best_topic(self) -> TopicIdea:
        """ดึง topic ที่ดีที่สุดจากทุกแหล่ง โดยลำดับความสำคัญ"""

        # 1. ปฏิทินไทย — ถ้าวันนี้มีเทศกาล ใช้ก่อนเลย
        calendar_topic = self._check_calendar()
        if calendar_topic:
            logger.info(f"[Source: Calendar] {calendar_topic.title}")
            return calendar_topic

        # 2. Google Trends — หัวข้อที่คนค้นหามากวันนี้
        trends_topic = self._get_google_trends()
        if trends_topic:
            logger.info(f"[Source: Google Trends] {trends_topic.title}")
            return trends_topic

        # 3. RSS ข่าว — หัวข้อข่าวล่าสุดที่เกี่ยวข้อง
        rss_topic = self._get_rss_news()
        if rss_topic:
            logger.info(f"[Source: RSS] {rss_topic.title}")
            return rss_topic

        # 4. Evergreen — fallback เสมอ
        ev_topic = self._get_evergreen()
        logger.info(f"[Source: Evergreen] {ev_topic.title}")
        return ev_topic

    def _check_calendar(self) -> Optional[TopicIdea]:
        today = datetime.date.today()
        key = (today.month, today.day)
        event = THAI_CALENDAR.get(key)
        if not event:
            # เช็คล่วงหน้า 1 วันด้วย
            tomorrow = today + datetime.timedelta(days=1)
            event = THAI_CALENDAR.get((tomorrow.month, tomorrow.day))
            if event:
                event = f"เตรียมตัวรับ{event} พรุ่งนี้"
        if event:
            return TopicIdea(
                title=f"{event} กับ{self.niche}: สิ่งที่คุณควรรู้",
                source="ปฏิทินไทย",
                keywords=[event],
            )
        return None

    def _get_google_trends(self) -> Optional[TopicIdea]:
        try:
            from pytrends.request import TrendReq
            pt = TrendReq(hl="th-TH", tz=420, timeout=(5, 10))
            trending = pt.trending_searches(pn="thailand")
            if trending is None or trending.empty:
                return None

            candidates = trending[0].tolist()[:10]
            # กรองหา trend ที่เกี่ยวกับ niche
            niche_keywords = self.niche.lower().split()
            for trend in candidates:
                for kw in niche_keywords:
                    if kw in trend.lower():
                        return TopicIdea(
                            title=f"ทำไม '{trend}' ถึงกำลังฮิต และเกี่ยวกับ{self.niche}อย่างไร",
                            source="Google Trends",
                            keywords=[trend],
                        )

            # ถ้าไม่มีที่เกี่ยวข้องโดยตรง สุ่มจาก top 5 แล้วเชื่อมกับ niche
            top_trend = random.choice(candidates[:5])
            return TopicIdea(
                title=f"กระแส '{top_trend}' มีผลต่อ{self.niche}อย่างไร",
                source="Google Trends",
                keywords=[top_trend],
            )
        except Exception as e:
            logger.debug(f"Google Trends error: {e}")
            return None

    def _get_rss_news(self) -> Optional[TopicIdea]:
        import requests as req

        # ลอง niche-specific RSS ก่อน
        niche_feeds = []
        for key, feeds in NICHE_RSS.items():
            if key in self.niche:
                niche_feeds = feeds
                break

        all_feeds = list(niche_feeds) + list(RSS_FEEDS.values())
        random.shuffle(all_feeds)

        headers = {"User-Agent": "Mozilla/5.0 (compatible; AutoPoster/1.0)"}

        for url in all_feeds[:4]:
            try:
                r = req.get(url, timeout=8, headers=headers)
                feed = feedparser.parse(r.content)
                if not feed.entries:
                    continue
                entry = random.choice(feed.entries[:10])
                title = entry.get("title", "").strip()
                if len(title) < 8:
                    continue
                feed_name = feed.feed.get("title", "ข่าว")
                return TopicIdea(
                    title=f"วิเคราะห์: {title} — สิ่งที่ต้องรู้เกี่ยวกับ{self.niche}",
                    source=f"RSS:{feed_name}",
                    keywords=[title[:40]],
                )
            except Exception as e:
                logger.debug(f"RSS error {url}: {e}")
                continue
        return None

    def _get_evergreen(self) -> TopicIdea:
        # หา evergreen ที่ตรงกับ niche มากที่สุด
        for key, topics in EVERGREEN.items():
            if key in self.niche or any(k in self.niche for k in key.split("และ")):
                topic = random.choice(topics)
                return TopicIdea(title=topic, source="Evergreen", keywords=[])

        # ถ้าไม่เจอ niche ที่ตรง สร้างจาก template
        templates = [
            f"5 สิ่งที่ต้องรู้เกี่ยวกับ{self.niche}ในปี {datetime.date.today().year}",
            f"เริ่มต้น{self.niche}อย่างไรให้ได้ผลจริง",
            f"ข้อผิดพลาดที่คนมักทำเกี่ยวกับ{self.niche}",
            f"เคล็ดลับ{self.niche}ที่ผู้เชี่ยวชาญใช้",
            f"{self.niche} สิ่งที่คุณยังไม่รู้",
        ]
        return TopicIdea(
            title=random.choice(templates),
            source="Template",
            keywords=[],
        )
