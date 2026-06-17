"""
Interactive Setup Wizard
รัน: python setup_wizard.py
- เปิดเบราว์เซอร์ให้อัตโนมัติ
- ถามแค่ API keys
- ทดสอบทุก key ก่อนบันทึก
- สร้าง .env ให้เอง
"""
import os
import sys
import io
import time
import webbrowser
import requests
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ============ COLORS ============
G = "\033[92m"   # green
R = "\033[91m"   # red
Y = "\033[93m"   # yellow
B = "\033[94m"   # blue
C = "\033[96m"   # cyan
W = "\033[97m"   # white
BOLD = "\033[1m"
DIM = "\033[2m"
X = "\033[0m"    # reset


def banner():
    print(f"""
{B}{BOLD}╔══════════════════════════════════════════════════╗
║        AUTO SOCIAL MEDIA POSTER — SETUP         ║
║              ฟรี 100% ไม่มีค่าใช้จ่าย           ║
╚══════════════════════════════════════════════════╝{X}
""")


def section(num: int, title: str, subtitle: str = ""):
    print(f"\n{B}{BOLD}[{num}] {title}{X}")
    if subtitle:
        print(f"    {DIM}{subtitle}{X}")
    print(f"    {'─'*46}")


def ok(msg): print(f"    {G}✓ {msg}{X}")
def err(msg): print(f"    {R}✗ {msg}{X}")
def info(msg): print(f"    {C}→ {msg}{X}")
def warn(msg): print(f"    {Y}! {msg}{X}")


def ask(prompt: str, secret: bool = False) -> str:
    print(f"\n    {W}{prompt}{X}")
    print(f"    {DIM}(วาง key แล้วกด Enter){X}" if not secret else "")
    val = input(f"    > ").strip()
    return val


def open_browser(url: str, label: str):
    print(f"\n    {C}→ กำลังเปิด {label}...{X}")
    time.sleep(0.5)
    webbrowser.open(url)
    time.sleep(1)


def test_gemini(key: str) -> bool:
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content("ตอบว่า OK เท่านั้น")
        return "OK" in resp.text.upper() or len(resp.text) > 0
    except Exception as e:
        err(f"Gemini test failed: {e}")
        return False


def test_facebook(page_id: str, token: str) -> bool:
    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{page_id}",
            params={"access_token": token, "fields": "name"},
            timeout=10,
        )
        data = r.json()
        if "name" in data:
            ok(f"Facebook Page: {data['name']}")
            return True
        err(f"Facebook: {data.get('error', {}).get('message', 'unknown error')}")
        return False
    except Exception as e:
        err(f"Facebook test failed: {e}")
        return False


def test_line(token: str) -> bool:
    try:
        r = requests.get(
            "https://api.line.me/v2/bot/info",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        data = r.json()
        if "displayName" in data:
            ok(f"LINE Bot: {data['displayName']}")
            return True
        err(f"LINE: {data.get('message', 'invalid token')}")
        return False
    except Exception as e:
        err(f"LINE test failed: {e}")
        return False


def save_env(config: dict):
    lines = [
        "# Auto Poster — สร้างโดย setup_wizard.py\n\n",
        f"GEMINI_API_KEY={config.get('gemini', '')}\n\n",
        f"FACEBOOK_PAGE_ID={config.get('fb_page', '')}\n",
        f"FACEBOOK_ACCESS_TOKEN={config.get('fb_token', '')}\n\n",
        f"LINE_CHANNEL_ACCESS_TOKEN={config.get('line_token', '')}\n\n",
        f"TIKTOK_ACCESS_TOKEN={config.get('tiktok_token', '')}\n\n",
        f"CONTENT_NICHE={config.get('niche', 'ความรู้การเงินและการลงทุน')}\n\n",
        f"ENABLE_FACEBOOK={'true' if config.get('fb_page') else 'false'}\n",
        f"ENABLE_LINE={'true' if config.get('line_token') else 'false'}\n",
        f"ENABLE_TIKTOK={'true' if config.get('tiktok_token') else 'false'}\n",
    ]
    with open(".env", "w", encoding="utf-8") as f:
        f.writelines(lines)
    ok(".env บันทึกแล้ว")


def main():
    os.chdir(Path(__file__).parent)
    banner()
    config = {}

    print(f"{Y}การ setup จะใช้เวลาประมาณ 15-20 นาที{X}")
    print(f"{Y}ระบบจะเปิดเบราว์เซอร์ให้อัตโนมัติ คุณต้องแค่ copy-paste key{X}")
    input(f"\n{BOLD}กด Enter เพื่อเริ่ม...{X} ")

    # ============================================================
    # STEP 1: CONTENT NICHE
    # ============================================================
    section(1, "เลือก Niche ของ Content", "หัวข้อหลักที่ AI จะสร้าง content ให้")
    niches = [
        "ความรู้การเงินและการลงทุน",
        "สุขภาพและการออกกำลังกาย",
        "เทคโนโลยีและ AI",
        "ท่องเที่ยวไทย",
        "ความงามและสกินแคร์",
        "อาหารและการทำอาหาร",
        "พัฒนาตัวเอง",
    ]
    print(f"\n    {W}เลือก niche:{X}")
    for i, n in enumerate(niches, 1):
        print(f"    {C}{i}.{X} {n}")
    print(f"    {C}8.{X} พิมพ์เอง")

    choice = input(f"\n    > เลือกหมายเลข (1-8): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= 7:
        config["niche"] = niches[int(choice) - 1]
    else:
        config["niche"] = input(f"    > พิมพ์ niche ของคุณ: ").strip() or niches[0]
    ok(f"Niche: {config['niche']}")

    # ============================================================
    # STEP 2: GEMINI API KEY
    # ============================================================
    section(2, "Google Gemini API Key", "ฟรี 1,500 req/วัน — ใช้สร้าง content")

    info("เปิดเว็บ Google AI Studio...")
    open_browser("https://aistudio.google.com/apikey", "Google AI Studio")

    print(f"""
    {W}ขั้นตอน:{X}
    1. Login ด้วย Google Account
    2. คลิก {Y}"Create API key"{X}
    3. คลิก {Y}"Create API key in new project"{X}
    4. Copy key ที่ขึ้นต้นด้วย {Y}AIza...{X}
    """)

    for attempt in range(3):
        key = ask("วาง Gemini API Key ที่นี่:")
        if not key.startswith("AIza"):
            warn("Key ต้องขึ้นต้นด้วย 'AIza' ลองใหม่")
            continue
        print(f"    {C}กำลังทดสอบ key...{X}")
        if test_gemini(key):
            ok("Gemini API ใช้งานได้!")
            config["gemini"] = key
            break
        else:
            warn(f"ลองอีกครั้ง ({attempt+1}/3)")
    else:
        warn("ข้าม Gemini — ใส่ key ในไฟล์ .env ได้ภายหลัง")
        config["gemini"] = ""

    # ============================================================
    # STEP 3: FACEBOOK
    # ============================================================
    section(3, "Facebook Page Access Token", "โพสต์อัตโนมัติลง Facebook Page")

    print(f"\n    {W}ต้องการ Facebook Page หรือไม่?{X}")
    fb_choice = input("    (y/n): ").strip().lower()

    if fb_choice == "y":
        info("เปิด Facebook Developers...")
        open_browser("https://developers.facebook.com/tools/explorer/", "Graph API Explorer")

        print(f"""
    {W}ขั้นตอน:{X}
    1. Login ด้วย Facebook
    2. คลิก {Y}"Add a Permission"{X} → เพิ่ม:
       • pages_manage_posts
       • pages_read_engagement
    3. คลิก {Y}"Generate Access Token"{X}
    4. เลือก Page ของคุณ → อนุญาต
    5. Copy Token
    """)
        fb_token = ask("วาง Facebook Access Token:")
        fb_page = ask("วาง Facebook Page ID (ตัวเลข):")

        if fb_token and fb_page:
            print(f"    {C}กำลังทดสอบ...{X}")
            if test_facebook(fb_page, fb_token):
                config["fb_token"] = fb_token
                config["fb_page"] = fb_page
            else:
                warn("Facebook token อาจมีปัญหา — บันทึกไว้ก่อน ตรวจสอบ permission อีกครั้ง")
                config["fb_token"] = fb_token
                config["fb_page"] = fb_page
    else:
        config["fb_token"] = ""
        config["fb_page"] = ""
        info("ข้าม Facebook")

    # ============================================================
    # STEP 4: LINE
    # ============================================================
    section(4, "LINE Official Account", "ฟรี 200 messages/เดือน")

    print(f"\n    {W}ต้องการ LINE หรือไม่?{X}")
    line_choice = input("    (y/n): ").strip().lower()

    if line_choice == "y":
        info("เปิด LINE Developers Console...")
        open_browser("https://developers.line.biz/console/", "LINE Developers")

        print(f"""
    {W}ขั้นตอน:{X}
    1. Login ด้วย LINE account
    2. คลิก {Y}"Create a new provider"{X} → ตั้งชื่อ
    3. คลิก {Y}"Create a Messaging API channel"{X}
    4. กรอกข้อมูล channel → Create
    5. ไปที่แถบ {Y}"Messaging API"{X}
    6. เลื่อนลงหา {Y}"Channel access token"{X}
    7. คลิก {Y}"Issue"{X} → Copy token
    """)
        line_token = ask("วาง LINE Channel Access Token:")

        if line_token:
            print(f"    {C}กำลังทดสอบ...{X}")
            if test_line(line_token):
                config["line_token"] = line_token
            else:
                warn("LINE token อาจมีปัญหา — บันทึกไว้ก่อน")
                config["line_token"] = line_token
    else:
        config["line_token"] = ""
        info("ข้าม LINE")

    config["tiktok_token"] = ""

    # ============================================================
    # SAVE .env
    # ============================================================
    section(5, "บันทึก Configuration")
    save_env(config)

    # ============================================================
    # SUMMARY
    # ============================================================
    print(f"""
{B}{BOLD}╔══════════════════════════════════════════════════╗
║                   Setup เสร็จแล้ว!              ║
╚══════════════════════════════════════════════════╝{X}

    {G}✓{X} Gemini API  : {'พร้อม' if config.get('gemini') else Y+'ยังไม่ได้ตั้งค่า'+X}
    {G}✓{X} Facebook    : {'พร้อม' if config.get('fb_token') else Y+'ยังไม่ได้ตั้งค่า'+X}
    {G}✓{X} LINE        : {'พร้อม' if config.get('line_token') else Y+'ยังไม่ได้ตั้งค่า'+X}

    {W}คำสั่งถัดไป:{X}

    {C}ทดสอบโพสต์ทันที:{X}
      python main.py --now

    {C}รัน scheduler ตลอด 24/7 (local):{X}
      python main.py --schedule

    {C}ตั้ง GitHub Actions (โพสต์บน cloud ฟรี):{X}
      python github_setup.py
""")


if __name__ == "__main__":
    main()
