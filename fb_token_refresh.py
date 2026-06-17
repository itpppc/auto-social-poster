# -*- coding: utf-8 -*-
"""
Facebook Token Refresher — แลก short-lived token → long-lived → Page tokens ที่ไม่หมดอายุ

ใช้: รัน python fb_token_refresh.py
ต้องการ:
  1. APP_ID + APP_SECRET ของ Facebook App
  2. User Access Token (short-lived) จาก Graph API Explorer

ขั้นตอน:
  1. ไปที่ https://developers.facebook.com/tools/explorer/
  2. เลือก App ของคุณ มุมขวาบน
  3. ติ๊ก permissions: pages_show_list, pages_manage_posts, pages_read_engagement
  4. กด "Generate Access Token" → copy
  5. รัน script นี้ → วาง token + app credentials
  6. Script จะแลกเป็น Page Tokens ที่ไม่หมดอายุ → บันทึก .env
"""
import os
import re
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stdin.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

GRAPH = "https://graph.facebook.com/v21.0"


def update_env(updates: dict):
    """อัปเดต .env file"""
    content = ENV_PATH.read_text(encoding="utf-8")
    for key, val in updates.items():
        pattern = rf"^{re.escape(key)}=.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{key}={val}", content, flags=re.MULTILINE)
        else:
            content += f"\n{key}={val}"
    ENV_PATH.write_text(content, encoding="utf-8")


def main():
    print("\n" + "=" * 65)
    print("  Facebook Token Refresher — ต่ออายุ Page Tokens")
    print("=" * 65)

    # 1. Get APP_ID and APP_SECRET
    app_id     = os.getenv("FACEBOOK_APP_ID", "")
    app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not app_id:
        print("\n[1] APP_ID ของ Facebook App")
        print("    หา: https://developers.facebook.com/apps/ → App settings → Basic → App ID")
        app_id = input("    APP_ID: ").strip()
    if not app_secret:
        print("\n[2] APP_SECRET ของ Facebook App")
        print("    (ใน App settings → Basic → App Secret → Show)")
        app_secret = input("    APP_SECRET: ").strip()

    if not (app_id and app_secret):
        print("ERROR: ต้องการ APP_ID + APP_SECRET")
        sys.exit(1)

    # 2. Short-lived User Token
    print("\n[3] User Access Token (short-lived)")
    print("    หา: https://developers.facebook.com/tools/explorer/")
    print("    - เลือก App ของคุณ มุมขวาบน")
    print("    - ติ๊ก: pages_show_list, pages_manage_posts, pages_read_engagement")
    print("    - กด Generate Access Token → Copy ทั้งหมด")
    short_token = input("    Short-lived User Token: ").strip()
    if not short_token:
        print("ERROR: ไม่มี token")
        sys.exit(1)

    # 3. Exchange to Long-Lived User Token (60 days)
    print("\nแลก → Long-Lived User Token (60 วัน)...")
    r = requests.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type":        "fb_exchange_token",
        "client_id":         app_id,
        "client_secret":     app_secret,
        "fb_exchange_token": short_token,
    }, timeout=15)
    data = r.json()
    if "access_token" not in data:
        print(f"ERROR: {data}")
        sys.exit(1)
    long_user_token = data["access_token"]
    expires_in_days = data.get("expires_in", 0) // 86400
    print(f"✅ Long-Lived User Token (หมดอายุ {expires_in_days} วัน)")

    # 4. Get Page Tokens (never expire if from long-lived user token)
    print("\nดึง Page Access Tokens (ไม่หมดอายุ)...")
    r = requests.get(f"{GRAPH}/me/accounts", params={
        "access_token": long_user_token,
        "fields":       "id,name,access_token,category",
    }, timeout=15)
    data = r.json()
    pages = data.get("data", [])
    if not pages:
        print(f"ERROR: ไม่พบ Page — {data}")
        sys.exit(1)

    print(f"\nพบ {len(pages)} Pages:")
    for i, p in enumerate(pages, 1):
        print(f"  {i}. {p['name']} (ID: {p['id']})")

    # 5. Read existing FACEBOOK_PAGES to keep niche
    existing_pages_env = os.getenv("FACEBOOK_PAGES", "")
    existing_niches = {}
    if existing_pages_env:
        for entry in existing_pages_env.split(","):
            parts = entry.strip().split(":", 2)
            if len(parts) >= 3:
                existing_niches[parts[0]] = parts[2]

    # 6. Build new FACEBOOK_PAGES string with new tokens + preserved niches
    new_pages = []
    for p in pages:
        page_id = p["id"]
        page_token = p["access_token"]
        niche = existing_niches.get(page_id, p["name"])
        new_pages.append(f"{page_id}:{page_token}:{niche}")
    new_pages_str = ",".join(new_pages)

    # 7. Save to .env
    update_env({
        "FACEBOOK_APP_ID":         app_id,
        "FACEBOOK_APP_SECRET":     app_secret,
        "FACEBOOK_PAGES":          new_pages_str,
        "FACEBOOK_PAGE_ID":        pages[0]["id"],
        "FACEBOOK_ACCESS_TOKEN":   pages[0]["access_token"],
    })

    print("\n" + "=" * 65)
    print("  ✅ เรียบร้อย! บันทึกใน .env แล้ว")
    print("=" * 65)
    print("  - Long-Lived User Token: หมดอายุ 60 วัน")
    print("  - Page Access Tokens: ไม่หมดอายุ (ถ้า Page ไม่ถูก revoke)")
    print(f"  - บันทึก {len(pages)} Pages พร้อม niche")
    print("\n  Restart service เพื่อเริ่มโพสต์ Facebook")


if __name__ == "__main__":
    main()
