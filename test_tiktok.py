# -*- coding: utf-8 -*-
import os, sys, re, secrets, hashlib, base64, requests, tempfile, io
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stdin.reconfigure(encoding="utf-8", errors="replace")

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
ACCESS_TOKEN  = os.getenv("TIKTOK_ACCESS_TOKEN", "")
PEXELS_KEY    = os.getenv("PEXELS_API_KEY", "")

REDIRECT_URI = "https://www.tiktok.com/@ton.ai.40"
TOKEN_URL    = "https://open.tiktokapis.com/v2/oauth/token/"
AUTH_URL     = "https://www.tiktok.com/v2/auth/authorize/"
API_BASE     = "https://open.tiktokapis.com/v2"


def do_auth() -> str:
    print("\n" + "=" * 60)
    print("  TikTok Auth -- need Access Token")
    print("=" * 60)
    code_verifier  = secrets.token_urlsafe(64)
    digest         = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    state          = secrets.token_urlsafe(12)
    params = {
        "client_key": CLIENT_KEY,
        "scope": "video.publish,video.upload,user.info.basic",
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    print("\nOpen this URL in browser:\n")
    print(AUTH_URL + "?" + urlencode(params))
    print("\nAfter Authorize >> copy full URL from address bar")
    redirect_url = input("\nPaste redirect URL:\n> ").strip()
    try:
        qs = parse_qs(urlparse(redirect_url).query)
        code = qs.get("code", [None])[0] or redirect_url.strip()
    except Exception:
        code = redirect_url.strip()
    r = requests.post(TOKEN_URL, data={
        "client_key": CLIENT_KEY, "client_secret": CLIENT_SECRET,
        "code": code, "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI, "code_verifier": code_verifier,
    }, timeout=15)
    result = r.json()
    print(f"Auth response: {result}")
    if "access_token" not in result:
        sys.exit(1)
    token = result["access_token"]
    content = ENV_PATH.read_text(encoding="utf-8")
    content = re.sub(r"TIKTOK_ACCESS_TOKEN=[^\r\n]*", f"TIKTOK_ACCESS_TOKEN={token}", content)
    content = re.sub(r"ENABLE_TIKTOK=false", "ENABLE_TIKTOK=true", content)
    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"OK Token saved! expires: {result.get('expires_in',0)//86400} days")
    return token


def get_pexels_images(query="finance investment money", count=5):
    if not PEXELS_KEY:
        return ["https://images.pexels.com/photos/534216/pexels-photo-534216.jpeg",
                "https://images.pexels.com/photos/210990/pexels-photo-210990.jpeg",
                "https://images.pexels.com/photos/1020323/pexels-photo-1020323.jpeg"]
    r = requests.get("https://api.pexels.com/v1/search",
        headers={"Authorization": PEXELS_KEY},
        params={"query": query, "per_page": count, "orientation": "portrait"}, timeout=10)
    photos = r.json().get("photos", [])
    urls = [p["src"]["large2x"] for p in photos]
    print(f"Pexels: {len(urls)} images")
    return urls


def create_slideshow_video(image_urls, seconds_per_image=3, fps=24):
    """Download images and create MP4 slideshow"""
    import imageio
    import numpy as np
    from PIL import Image

    TARGET_W, TARGET_H = 1080, 1920

    print(f"Creating slideshow from {len(image_urls)} images...")
    output_path = Path(tempfile.gettempdir()) / "tonai_tiktok.mp4"

    writer = imageio.get_writer(
        str(output_path), fps=fps, codec="libx264",
        output_params=["-pix_fmt", "yuv420p", "-crf", "28"]
    )

    for i, url in enumerate(image_urls):
        print(f"  Downloading image {i+1}/{len(image_urls)}...")
        try:
            resp = requests.get(url, timeout=15)
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")

            # Crop to vertical 9:16
            w, h = img.size
            target_ratio = TARGET_W / TARGET_H
            current_ratio = w / h
            if current_ratio > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))

            img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
            frame = np.array(img)

            for _ in range(fps * seconds_per_image):
                writer.append_data(frame)
        except Exception as e:
            print(f"  Skip image {i+1}: {e}")

    writer.close()
    size = output_path.stat().st_size
    print(f"Video created: {output_path} ({size//1024} KB)")
    return str(output_path), size


def upload_video_to_tiktok(token, video_path, video_size, title):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Step 1: Init upload
    print("\nStep 1: Init upload...")
    init_payload = {
        "post_info": {
            "title": title[:150],
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1,
        },
    }
    r = requests.post(f"{API_BASE}/post/publish/video/init/",
                      headers=headers, json=init_payload, timeout=30)
    init_data = r.json()
    print(f"Init response: {init_data}")

    err = init_data.get("error", {})
    if err.get("code") != "ok":
        return init_data

    publish_id  = init_data["data"]["publish_id"]
    upload_url  = init_data["data"]["upload_url"]

    # Step 2: Upload file
    print(f"\nStep 2: Uploading video ({video_size//1024} KB)...")
    with open(video_path, "rb") as f:
        video_data = f.read()

    upload_headers = {
        "Content-Range": f"bytes 0-{video_size-1}/{video_size}",
        "Content-Type":  "video/mp4",
        "Content-Length": str(video_size),
    }
    r2 = requests.put(upload_url, headers=upload_headers, data=video_data, timeout=120)
    print(f"Upload HTTP: {r2.status_code}")

    if r2.status_code in [200, 201, 206]:
        print(f"\nSUCCESS! publish_id: {publish_id}")
        print("Wait 1-2 min then check TikTok @ton.ai.40")
        return {"status": "success", "publish_id": publish_id}
    else:
        return {"status": "failed", "http": r2.status_code, "body": r2.text[:200]}


# ── MAIN ──
if not CLIENT_KEY:
    print("ERROR: TIKTOK_CLIENT_KEY not set")
    sys.exit(1)

token = ACCESS_TOKEN if ACCESS_TOKEN else do_auth()

print("\n" + "=" * 60)
print("  TikTok Video Slideshow Upload Test")
print("=" * 60)

image_urls = get_pexels_images("finance investment money thailand", count=3)

video_path, video_size = create_slideshow_video(image_urls, seconds_per_image=3)

result = upload_video_to_tiktok(
    token, video_path, video_size,
    title="Investment tips for financial freedom #TonAI #finance"
)

print(f"\nFinal result: {result}")
