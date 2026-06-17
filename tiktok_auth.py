# -*- coding: utf-8 -*-
"""
TikTok OAuth Helper (PKCE + Manual Code) — รับ Access Token
รัน: python tiktok_auth.py
"""
import os, sys, secrets, hashlib, base64, re, requests
from urllib.parse import urlparse, parse_qs, urlencode
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI  = "https://www.tiktok.com/@ton.ai.40"
SCOPES        = "video.publish,video.upload,user.info.basic"
TOKEN_URL     = "https://open.tiktokapis.com/v2/oauth/token/"
AUTH_URL      = "https://www.tiktok.com/v2/auth/authorize/"

# PKCE
STATE          = secrets.token_urlsafe(12)
CODE_VERIFIER  = secrets.token_urlsafe(64)
_digest        = hashlib.sha256(CODE_VERIFIER.encode()).digest()
CODE_CHALLENGE = base64.urlsafe_b64encode(_digest).decode().rstrip("=")

if not CLIENT_KEY:
    print("ERROR: TIKTOK_CLIENT_KEY not set in .env")
    sys.exit(1)

params = {
    "client_key":            CLIENT_KEY,
    "scope":                 SCOPES,
    "response_type":         "code",
    "redirect_uri":          REDIRECT_URI,
    "state":                 STATE,
    "code_challenge":        CODE_CHALLENGE,
    "code_challenge_method": "S256",
}
url = AUTH_URL + "?" + urlencode(params)

print("\n" + "=" * 65, flush=True)
print("  TikTok Auth (PKCE) — Step-by-step", flush=True)
print("=" * 65, flush=True)
print(f"\n[1] ตั้งค่า Redirect URI ใน TikTok Developer ให้เป็น:", flush=True)
print(f"    {REDIRECT_URI}", flush=True)
print(f"\n[2] เปิด URL นี้ใน browser แล้ว login @ton.ai.40:", flush=True)
print(f"\n{url}\n", flush=True)
print("[3] หลัง Authorize → browser จะ redirect ไปหน้า @ton.ai.40", flush=True)
print("    URL ใน address bar จะมี ?code=xxxx&state=xxx", flush=True)
print("    Copy URL ทั้งหมดจาก address bar", flush=True)
print("=" * 65, flush=True)

redirect_url = input("\n[4] วาง URL ที่ redirect มา (full URL from address bar):\n> ").strip()

# Extract code from URL
try:
    qs   = parse_qs(urlparse(redirect_url).query)
    code = qs.get("code", [None])[0]
    if not code:
        # Maybe user pasted just the code
        code = redirect_url.strip()
except Exception:
    code = redirect_url.strip()

if not code:
    print("ERROR: ไม่พบ code ใน URL")
    sys.exit(1)

print(f"\nCode: {code[:20]}... กำลังแลก token...", flush=True)

r = requests.post(TOKEN_URL, data={
    "client_key":    CLIENT_KEY,
    "client_secret": CLIENT_SECRET,
    "code":          code,
    "grant_type":    "authorization_code",
    "redirect_uri":  REDIRECT_URI,
    "code_verifier": CODE_VERIFIER,
}, timeout=15)
result = r.json()

if "access_token" in result:
    import time
    token         = result["access_token"]
    refresh_token = result.get("refresh_token", "")
    expires_in    = result.get("expires_in", 86400)
    expires_at    = int(time.time() + expires_in)
    refresh_days  = result.get("refresh_expires_in", 0) // 86400

    print(f"\n✅ SUCCESS!", flush=True)
    print(f"   Access Token : {token[:30]}... (หมดอายุใน {expires_in//86400} วัน)", flush=True)
    print(f"   Refresh Token: {refresh_token[:30]}... (หมดอายุใน {refresh_days} วัน)", flush=True)

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Update or append each token field
    updates = {
        "TIKTOK_ACCESS_TOKEN":     token,
        "TIKTOK_REFRESH_TOKEN":    refresh_token,
        "TIKTOK_TOKEN_EXPIRES_AT": str(expires_at),
    }
    for key, val in updates.items():
        pattern = rf"{key}=[^\r\n]*"
        if re.search(pattern, content):
            content = re.sub(pattern, f"{key}={val}", content)
        else:
            content += f"\n{key}={val}"
    content = re.sub(r"ENABLE_TIKTOK=false", "ENABLE_TIKTOK=true", content)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("\n   ✅ บันทึก access_token + refresh_token ใน .env แล้ว", flush=True)
    print("   ✅ เปิด ENABLE_TIKTOK=true", flush=True)
    print("   ✅ ระบบจะ auto-refresh access_token ทุก 24 ชม. โดยอัตโนมัติ", flush=True)
    print("\n   Restart service เพื่อเริ่มโพส TikTok!", flush=True)
else:
    print(f"\n❌ ERROR: {result}", flush=True)
    if result.get("error") == "invalid_grant":
        print("   Code หมดอายุ — ลอง Step 2 ใหม่อีกครั้ง", flush=True)
