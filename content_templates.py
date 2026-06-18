# -*- coding: utf-8 -*-
"""
Content Templates — fallback content เมื่อ AI quota หมด
แต่ละ niche มี templates หลายแบบ + random pick + topic substitution
ผลลัพธ์: ระบบยังโพสต์ได้แม้ Gemini fail
"""
import random
from typing import Dict, List


# ─────────────────────────────────────────────────
# TEMPLATES แยกตาม niche
# ─────────────────────────────────────────────────

NICHE_KEYWORDS = {
    "tonai_tech": ["smart factory","iot","oee","cctv","ai","cybersecurity","server","network","custom software","ไอที","คอมพิวเตอร์","โน๊ตบุ๊ค"],
    "seafood": ["ขนมจีน","น้ำยา","อาหารใต้","อาหารทะเล","seafood","ปลา","กุ้ง"],
    "studio": ["studio","ภาพถ่าย","photography","social media","facebook ads","tiktok","instagram","การตลาด","marketing"],
    "salad": ["สลัด","คลีน","ผักออร์แกนิค","ผักไฮโดรโปนิค","organic","สุขภาพ","delivery"],
}

def detect_niche(text: str) -> str:
    """ตรวจว่า niche/topic ตรงกับกลุ่มไหน"""
    t = text.lower()
    for niche_key, keywords in NICHE_KEYWORDS.items():
        if any(k.lower() in t for k in keywords):
            return niche_key
    return "tonai_tech"


# ─────────────────────────────────────────────────
# Templates — TON AI Tech (IT Solutions)
# ─────────────────────────────────────────────────
TEMPLATES_TONAI = [
    {
        "fb": """🚀 {topic}

หากคุณกำลังมองหาโซลูชัน IT ที่ตอบโจทย์ธุรกิจของคุณจริงๆ — TON AI Tech ช่วยได้

✅ Smart Factory & OEE Dashboard
✅ Smart Aqua Farm IoT
✅ Smart CCTV AI Detection
✅ Network & Server
✅ Cybersecurity
✅ Custom Software Development

💡 ทำไมต้อง TON AI Tech?
• Customize ตามความต้องการจริง — ไม่ใช่ Package สำเร็จรูป
• ออกแบบโดยผู้เชี่ยวชาญ ประสบการณ์ 10+ ปี
• Demo ฟรี — ดูจริงก่อนตัดสินใจ
• รองรับ ไทย/อังกฤษ/จีน

📞 ปรึกษาฟรี — ติดต่อเราตอนนี้!
📩 LINE: @itpppc
📲 โทร: 0909728573
🌐 https://ton-ai-tech.web.app

#TonAITech #SmartFactory #IoT #AISolutions""",
        "line": """🚀 {topic}

ปัญหา IT ทำให้ธุรกิจคุณช้าลง? ⏳
TON AI Tech ช่วยได้ ✨

• Smart Factory · OEE Dashboard
• IoT · CCTV AI · Network
• Custom Software ตามความต้องการ

💡 Demo ฟรี · ปรึกษาฟรี
📩 LINE @itpppc
📞 0909728573""",
        "tt": """🔥 {topic}

ลด Downtime 70% · เพิ่ม OEE 25%
TON AI Tech — โซลูชัน IT ครบวงจร
📩 LINE @itpppc · Demo ฟรี

#SmartFactory #IoT #TonAITech""",
    },
    {
        "fb": """💡 {topic}

เคยรู้สึกว่าธุรกิจเสียโอกาสเพราะระบบ IT ไม่ทันสมัย?

ที่ TON AI Tech เราพัฒนาระบบ Smart Factory, IoT และ AI ให้กับธุรกิจไทย — ออกแบบมาเฉพาะสำหรับคุณ ไม่ใช่ template สำเร็จรูป

🏭 Smart Factory · OEE Dashboard เห็นข้อมูล real-time
🌾 Smart Farm IoT ลดต้นทุน ลดความเสี่ยง
📹 Smart CCTV AI ตรวจจับแม่นยำ
🌐 Network & Server เสถียร ปลอดภัย

💰 ลูกค้าจริง: ลด Downtime ได้กว่า 70% · เพิ่มประสิทธิภาพ 25%

🎁 พิเศษ! Demo ฟรี — ดูระบบจริงก่อนตัดสินใจ ไม่ต้องเสี่ยง

📩 ปรึกษาฟรี LINE @itpppc
📞 โทร 0909728573

#TonAITech #SmartFactory #IoT #ระบบงานองค์กร""",
        "line": """💡 {topic}

ระบบ IT ของคุณยังตอบโจทย์อยู่ไหม? 🤔

TON AI Tech ออกแบบระบบให้ตรงธุรกิจคุณ:
• ลด Downtime 70%
• เพิ่ม OEE 25%
• Custom 100%

🎁 Demo ฟรี ดูจริงก่อนจ่าย
📩 LINE @itpppc""",
        "tt": """⚡ {topic}

ลูกค้าจริงลด Downtime 70% ใน 3 เดือน
TON AI Tech · Smart Factory IoT
📩 LINE @itpppc

#SmartFactory #IoT #ลดต้นทุน""",
    },
]

# ─────────────────────────────────────────────────
# Templates — Seafood / Khanom Jeen
# ─────────────────────────────────────────────────
TEMPLATES_SEAFOOD = [
    {
        "fb": """🐟 {topic}

อร่อยแบบสดใหม่ ส่งตรงจากทะเล!

ขนมจีนทะเลสด — น้ำยาเข้มข้น เนื้อปลาแน่น กุ้งสดทะเลใหม่ ปรุงตามสูตรอาหารใต้แท้ๆ

✨ จุดเด่น:
• วัตถุดิบสดใหม่จากทะเล
• สูตรลับสืบทอด อาหารใต้แท้
• ไม่มีผงชูรส ใช้แต่ของจริง
• พร้อมเสิร์ฟ ส่งทันใจ

🎁 ลูกค้าใหม่: ลด 10% สำหรับคำสั่งซื้อแรก

📩 สั่งเลย LINE: @itpppc
📞 โทร 0909728573

#ขนมจีนทะเลสด #อาหารทะเล #อาหารใต้ #อร่อย""",
        "line": """🐟 {topic}

ขนมจีนน้ำยาทะเลสด สูตรอาหารใต้แท้! ✨

• กุ้งสด ปลาสด จากทะเล
• น้ำยาเข้มข้น สูตรลับ
• ไม่ใส่ผงชูรส

🎁 ลด 10% ลูกค้าใหม่
📩 LINE @itpppc""",
        "tt": """🐟 {topic}

ขนมจีนน้ำยาทะเลสด · กุ้งสดปลาสด
สูตรอาหารใต้แท้ ส่งทันใจ
📩 LINE @itpppc

#ขนมจีน #อาหารทะเล #อาหารใต้""",
    },
]

# ─────────────────────────────────────────────────
# Templates — Salad / Healthy Food
# ─────────────────────────────────────────────────
TEMPLATES_SALAD = [
    {
        "fb": """🥗 {topic}

กินคลีน · ลดน้ำหนัก · สุขภาพดี — เริ่มต้นที่ "ผักจริง" ที่เราปลูกเอง!

ที่ พอสจิแซนวิสสลัดสด เราปลูกผักไฮโดรโปนิคไร้สารพิษเอง ด้วยระบบที่ควบคุมคุณภาพทุกขั้นตอน

✨ ทำไมต้องเรา:
• ผักออร์แกนิค ปลูกเอง ไร้สารเคมี
• สดใหม่ทุกวัน เก็บเช้า ส่งกลางวัน
• สลัดและแซนวิช อาหารคลีนพร้อมทาน
• Delivery ในกรุงเทพ

🎁 ลูกค้าใหม่: ส่งฟรีในเขตกรุงเทพ

📩 สั่งเลย LINE: @itpppc
📞 0909728573

#สลัด #อาหารคลีน #ผักออร์แกนิค #ผักไฮโดรโปนิค""",
        "line": """🥗 {topic}

สลัดผักออร์แกนิคปลูกเอง สดทุกวัน! 🌱

• ผักไฮโดรโปนิค ไร้สารพิษ
• แซนวิช · อาหารคลีน
• Delivery กรุงเทพ

🎁 ส่งฟรี ลูกค้าใหม่
📩 LINE @itpppc""",
        "tt": """🥗 {topic}

ผักออร์แกนิคปลูกเอง · ไร้สารพิษ
สลัด · แซนวิช · อาหารคลีน
📩 LINE @itpppc

#สลัด #ผักออร์แกนิค #อาหารคลีน""",
    },
]

# ─────────────────────────────────────────────────
# Templates — Marketing / Studio
# ─────────────────────────────────────────────────
TEMPLATES_STUDIO = [
    {
        "fb": """📈 {topic}

ขายของออนไลน์แต่ยอดไม่ขึ้น? ปัญหาอาจไม่ใช่ "ของ" แต่เป็น "การตลาด"!

Poshji Studio รับทำการตลาดออนไลน์ครบวงจร — ตั้งแต่วางกลยุทธ์ ทำคอนเทนต์ ยิงแอด ไปจนถึงปิดดีล

🎯 บริการของเรา:
• Facebook Ads · TikTok Ads · IG Ads
• Content Marketing · กลยุทธ์ดึงลูกค้า
• สร้างคอนเทนต์ภาพ/วิดีโอ
• Analytics · วัดผล ROI

💡 ลูกค้าจริง: เพิ่มยอดขาย 3 เท่าใน 2 เดือน

🎁 ปรึกษาฟรี · วางกลยุทธ์เบื้องต้นฟรี

📩 LINE: @itpppc
📞 0909728573

#การตลาดออนไลน์ #FacebookAds #TikTokAds #SocialMediaMarketing""",
        "line": """📈 {topic}

ขายของออนไลน์ยอดไม่ขึ้น? Poshji Studio ช่วยได้ 🎯

• Facebook/TikTok/IG Ads
• Content Marketing
• กลยุทธ์เพิ่มยอด 3 เท่า

🎁 ปรึกษาฟรี
📩 LINE @itpppc""",
        "tt": """📈 {topic}

ยอดขายเพิ่ม 3 เท่าใน 2 เดือน
Poshji Studio · การตลาดออนไลน์ครบ
📩 LINE @itpppc

#การตลาด #FacebookAds #TikTokAds""",
    },
]


TEMPLATE_MAP = {
    "tonai_tech": TEMPLATES_TONAI,
    "seafood": TEMPLATES_SEAFOOD,
    "salad": TEMPLATES_SALAD,
    "studio": TEMPLATES_STUDIO,
}


def get_fallback_content(topic: str, niche: str) -> Dict[str, any]:
    """คืน content แบบ template — ใช้เมื่อ AI ทำงานไม่ได้"""
    # Detect niche
    key = detect_niche(f"{topic} {niche}")
    templates = TEMPLATE_MAP.get(key, TEMPLATES_TONAI)
    tmpl = random.choice(templates)

    fb_text = tmpl["fb"].format(topic=topic[:100])
    line_text = tmpl["line"].format(topic=topic[:100])
    tt_text = tmpl["tt"].format(topic=topic[:100])

    hashtags_map = {
        "tonai_tech": ["#TonAITech", "#SmartFactory", "#IoT", "#AISolutions",
                       "#ITSolution", "#ระบบงานองค์กร", "#ผู้ประกอบการไทย", "#DigitalTransformation"],
        "seafood": ["#ขนมจีนทะเลสด", "#อาหารทะเล", "#อาหารใต้", "#อร่อย",
                    "#กรุงเทพ", "#delivery", "#ของกินไทย", "#อาหารพรีเมียม"],
        "salad": ["#สลัด", "#อาหารคลีน", "#ผักออร์แกนิค", "#ไฮโดรโปนิค",
                  "#สุขภาพดี", "#delivery", "#กรุงเทพ", "#ลดน้ำหนัก"],
        "studio": ["#การตลาดออนไลน์", "#FacebookAds", "#TikTokAds", "#SocialMediaMarketing",
                   "#เพิ่มยอดขาย", "#ผู้ประกอบการไทย", "#DigitalMarketing", "#ContentMarketing"],
    }
    hashtags = hashtags_map.get(key, hashtags_map["tonai_tech"])

    return {
        "facebook_post": fb_text,
        "line_message": line_text,
        "tiktok_script": tt_text,
        "hashtags": hashtags,
        "call_to_action": "📩 ทักไลน์ @itpppc ปรึกษาฟรี ทันที!",
    }
