"""
Dashboard Stats Server — รัน local เพื่อให้ workflow_diagram.html ดึงข้อมูล
รัน: python dashboard_server.py
เปิด: http://localhost:5001
"""
import json
import glob
import os
import socket
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
CORS(app)

# ═══ SECURITY: Host Guard ═══
# Tunnel (public) เข้าได้แค่ /line/webhook เท่านั้น — route อื่นเฉพาะ localhost
_LOCAL_HOSTS = {"localhost:5001", "127.0.0.1:5001", "localhost", "127.0.0.1"}
_PUBLIC_ALLOWED_PATHS = {"/line/webhook"}

@app.before_request
def _host_guard():
    from flask import request, abort
    host = (request.host or "").lower()
    if host not in _LOCAL_HOSTS and request.path not in _PUBLIC_ALLOWED_PATHS:
        abort(403)

@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers.pop("Server", None)
    return resp

# Redact tokens/keys จาก text ก่อนส่งออก
import re as _re_sec
_TOKEN_PATTERNS = [
    _re_sec.compile(r"EAA[0-9A-Za-z]{20,}"),        # Facebook tokens
    _re_sec.compile(r"AIza[0-9A-Za-z_\-]{30,}"),    # Google API keys
    _re_sec.compile(r"AQ\.[0-9A-Za-z_\-]{20,}"),    # Gemini keys
    _re_sec.compile(r"act\.[0-9A-Za-z!._\-]{20,}"), # TikTok access
    _re_sec.compile(r"rft\.[0-9A-Za-z!._\-]{20,}"), # TikTok refresh
    _re_sec.compile(r"Bearer\s+\S{15,}"),
]

def redact(text: str) -> str:
    for p in _TOKEN_PATTERNS:
        text = p.sub("[REDACTED]", text)
    return text

LOG_DIR   = BASE_DIR / "post_logs"
HTML_FILE = BASE_DIR / "workflow_diagram.html"


def parse_fb_pages() -> dict:
    """parse FACEBOOK_PAGES env -> {page_id: name}"""
    pages_env = os.getenv("FACEBOOK_PAGES", "")
    result = {}
    if not pages_env:
        return result
    for entry in pages_env.split(","):
        parts = entry.strip().split(":", 2)
        if len(parts) >= 3:
            result[parts[0]] = parts[2]
        elif len(parts) >= 1:
            result[parts[0]] = f"Page {parts[0][-4:]}"
    return result


FB_PAGE_NAMES = parse_fb_pages()


@app.route("/")
def index():
    if HTML_FILE.exists():
        return send_file(HTML_FILE)
    return "<h2>Ton.AI Dashboard</h2><p><a href='/api/stats'>API Stats</a></p>"


def read_logs(limit=200):
    files = sorted(glob.glob(str(LOG_DIR / "*.json")), reverse=True)[:limit]
    logs = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                logs.append(json.load(fp))
        except Exception:
            pass
    return logs


def extract_platforms(log: dict) -> list:
    """Extract detailed platform info per post"""
    platforms = []
    for r in log.get("results", []):
        if not isinstance(r, dict):
            continue
        plat = r.get("platform", "")
        if plat == "facebook":
            for pg in r.get("pages", []):
                pid = pg.get("page_id", "")
                platforms.append({
                    "platform": "facebook",
                    "page_id": pid,
                    "page_name": FB_PAGE_NAMES.get(pid, f"Page {pid[-4:] if pid else ''}"),
                    "post_id": pg.get("post_id", ""),
                    "niche": pg.get("niche", ""),
                    "has_image": pg.get("has_image", False),
                })
        elif plat == "line" or plat == "line_flex":
            platforms.append({
                "platform": "line",
                "status": r.get("status", "success"),
            })
        elif plat == "tiktok":
            platforms.append({
                "platform": "tiktok",
                "publish_id": r.get("publish_id", ""),
                "status": r.get("status", "success"),
            })
    return platforms


@app.route("/api/stats")
def stats():
    logs = read_logs(limit=200)
    today = datetime.now().strftime("%Y-%m-%d")

    total_runs   = len(logs)
    success_runs = sum(1 for l in logs if l.get("success_count", 0) > 0)
    today_runs   = [l for l in logs if l.get("timestamp", "").startswith(today)]

    # Per-platform counters
    fb_posts, line_posts, tiktok_posts = 0, 0, 0
    fb_per_page = defaultdict(int)
    fb_with_image = 0

    for l in logs:
        for r in l.get("results", []):
            if not isinstance(r, dict):
                continue
            plat = r.get("platform", "")
            if plat == "facebook":
                for pg in r.get("pages", []):
                    fb_posts += 1
                    pid = pg.get("page_id", "")
                    fb_per_page[pid] += 1
                    if pg.get("has_image"):
                        fb_with_image += 1
            elif plat in ("line", "line_flex"):
                line_posts += 1
            elif plat == "tiktok":
                tiktok_posts += 1

    # Per-page breakdown
    fb_pages_breakdown = [
        {"page_id": pid, "name": FB_PAGE_NAMES.get(pid, pid[-4:]), "count": cnt}
        for pid, cnt in sorted(fb_per_page.items(), key=lambda x: -x[1])
    ]

    # Last 7 days chart
    daily_counts = defaultdict(lambda: {"posts": 0, "success": 0, "errors": 0})
    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_counts[day] = {"posts": 0, "success": 0, "errors": 0}
    for l in logs:
        ts = l.get("timestamp", "")[:10]
        if ts in daily_counts:
            daily_counts[ts]["posts"]   += 1
            daily_counts[ts]["success"] += l.get("success_count", 0)
            daily_counts[ts]["errors"]  += l.get("error_count", 0)

    chart_data = [
        {"date": d, "label": datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m"),
         **daily_counts[d]}
        for d in sorted(daily_counts.keys())
    ]

    # Recent posts
    recent = []
    for l in logs[:30]:
        ts = l.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%d/%m %H:%M")
        except Exception:
            time_str = ts[:16]

        recent.append({
            "id":        ts.replace(":", "").replace(".", "").replace("-", ""),
            "time":      time_str,
            "timestamp": ts,
            "topic":     l.get("topic", l.get("content_topic", "—")),
            "source":    l.get("content", {}).get("source", ""),
            "success":   l.get("success_count", 0),
            "errors":    l.get("error_count", 0),
            "platforms": extract_platforms(l),
        })

    return jsonify({
        "total_runs":   total_runs,
        "success_runs": success_runs,
        "success_rate": round(success_runs / total_runs * 100) if total_runs else 0,
        "today_runs":   len(today_runs),
        "fb_posts":     fb_posts,
        "line_posts":   line_posts,
        "tiktok_posts": tiktok_posts,
        "fb_with_image": fb_with_image,
        "fb_pages":     fb_pages_breakdown,
        "chart":        chart_data,
        "recent":       recent,
    })


@app.route("/api/post/<post_id>")
def post_detail(post_id: str):
    """Get full content of a specific post"""
    logs = read_logs(limit=200)
    for l in logs:
        ts = l.get("timestamp", "")
        lid = ts.replace(":", "").replace(".", "").replace("-", "")
        if lid == post_id:
            l["platforms_detail"] = extract_platforms(l)
            return jsonify(l)
    return jsonify({"error": "not found"}), 404


@app.route("/api/log")
def get_log():
    log_file = BASE_DIR / "service.log"
    if not log_file.exists():
        return jsonify([])
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return jsonify([redact(l.rstrip()) for l in lines[-100:]])
    except Exception:
        return jsonify([])


# ────────────────────────────────────────────────────────
# REAL-TIME STATUS (n8n-style flow + content preview)
# ────────────────────────────────────────────────────────
@app.route("/api/status")
def get_current_status():
    import status_tracker as st
    return jsonify(st.get_status())


@app.route("/api/preview", methods=["POST"])
def trigger_preview():
    """สร้าง content preview แบบไม่โพสต์จริง — รันใน background thread"""
    import threading
    from config import Config
    from workflow import AutoPosterWorkflow

    def _bg():
        try:
            AutoPosterWorkflow(Config()).preview()
        except Exception as e:
            import status_tracker as st
            st.log(f"❌ Preview error: {e}", "error")
            st.finish_run()

    threading.Thread(target=_bg, daemon=True).start()
    return jsonify({"status": "preview_started"})


@app.route("/api/post-now", methods=["POST"])
def trigger_post_now():
    """รันโพสต์จริงทันที (manual trigger) — background"""
    import threading
    from config import Config
    from workflow import AutoPosterWorkflow

    def _bg():
        try:
            AutoPosterWorkflow(Config()).run(trigger="manual")
        except Exception as e:
            import status_tracker as st
            st.log(f"❌ Run error: {e}", "error")
            st.finish_run()

    threading.Thread(target=_bg, daemon=True).start()
    return jsonify({"status": "post_started"})


# ────────────────────────────────────────────────
# LINE Webhook — AI ตอบลูกค้าอัตโนมัติ
# ────────────────────────────────────────────────
@app.route("/line/webhook", methods=["POST"])
def line_webhook():
    """รับข้อความจากลูกค้าใน LINE → AI ตอบ"""
    try:
        from config import Config
        from line_ai_reply import handle_webhook
        body = request.get_data()
        signature = request.headers.get("X-Line-Signature", "")
        result = handle_webhook(Config(), body, signature)
        return jsonify(result), 200
    except Exception as e:
        import logging
        logging.getLogger("webhook").error(f"LINE webhook error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 200  # 200 กัน LINE retry


@app.route("/line/webhook", methods=["GET"])
def line_webhook_verify():
    """LINE verify endpoint"""
    return "LINE webhook OK", 200


def find_free_port(start=5001, end=5010):
    for p in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


if __name__ == "__main__":
    port = find_free_port()
    print(f"Dashboard -> http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
