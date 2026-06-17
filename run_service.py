# -*- coding: utf-8 -*-
"""
Ton.AI Auto Poster — Master Service
รวม Scheduler + Dashboard ในตัวเดียว
- Auto-restart เมื่อ crash (watchdog)
- รันได้โดยไม่ต้อง login Windows
รัน: python run_service.py
"""
import sys, os, time, threading, logging
from pathlib import Path

BASE = Path(__file__).parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

from dotenv import load_dotenv
load_dotenv(BASE / ".env")

# ── Logging ──────────────────────────────────────────────
LOG_FILE = BASE / "service.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("service")


# ── Services ─────────────────────────────────────────────

def run_scheduler():
    """APScheduler — โพสต์ตามเวลาที่กำหนด"""
    from config import Config
    from scheduler import AutoPosterScheduler
    config = Config()
    logger.info(f"Scheduler: โพสต์เวลา {config.post_times} (Asia/Bangkok)")
    AutoPosterScheduler(config).start()  # blocking


def run_dashboard():
    """Flask Dashboard — http://localhost:5001"""
    from dashboard_server import app
    logger.info("Dashboard: http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)


def run_manual_watcher():
    """Watch Firebase RTDB manual_queue → process manual posts from web"""
    from config import Config
    from content_generator import ContentGenerator
    import manual_watcher
    config = Config()
    generator = ContentGenerator(config)
    logger.info("ManualWatcher: เริ่มจับ manual_queue จาก Firebase")
    manual_watcher.watch_manual_queue(config, generator)  # blocking


# ── Watchdog ─────────────────────────────────────────────

def watchdog(name: str, fn):
    """Restart service on any crash with exponential backoff"""
    delay = 5
    while True:
        logger.info(f"[{name}] Starting service...")
        try:
            fn()
            logger.warning(f"[{name}] Exited normally.")
        except Exception as e:
            logger.error(f"[{name}] Crashed: {e}")
        logger.info(f"[{name}] Restarting in {delay}s...")
        time.sleep(delay)
        delay = min(delay * 2, 120)  # max 2 min between retries


# ── Main ─────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  Ton.AI Auto Poster Service v2.0")
    logger.info(f"  PID: {os.getpid()}")
    logger.info(f"  Log: {LOG_FILE}")
    logger.info("=" * 55)

    SERVICES = [
        ("Scheduler",     run_scheduler),
        ("Dashboard",     run_dashboard),
        ("ManualWatcher", run_manual_watcher),
    ]

    threads = []
    for name, fn in SERVICES:
        t = threading.Thread(
            target=watchdog, args=(name, fn),
            daemon=True, name=name
        )
        t.start()
        threads.append(t)
        time.sleep(0.5)

    logger.info(f"Started {len(threads)} services. Running...")

    try:
        while True:
            time.sleep(3600)
            alive = [t.name for t in threads if t.is_alive()]
            logger.info(f"[Heartbeat] Alive: {alive}")
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
        sys.exit(0)
