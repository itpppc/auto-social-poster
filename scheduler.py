"""
Scheduler — รันอัตโนมัติตามเวลาที่กำหนด
ใช้ APScheduler ทำงานเป็น background process
"""
import logging
import signal
import sys
import threading
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config
from workflow import AutoPosterWorkflow

logger = logging.getLogger(__name__)


class AutoPosterScheduler:
    def __init__(self, config: Config):
        self.config = config
        self.workflow = AutoPosterWorkflow(config)
        self.scheduler = BlockingScheduler(timezone="Asia/Bangkok")

    def setup_jobs(self):
        """เพิ่ม job ตามเวลาที่กำหนดใน config"""
        for time_str in self.config.post_times:
            hour, minute = time_str.split(":")
            self.scheduler.add_job(
                func=self._run_workflow,
                trigger=CronTrigger(hour=int(hour), minute=int(minute)),
                id=f"post_{time_str}",
                name=f"Auto Post at {time_str}",
                misfire_grace_time=300,  # รอได้สูงสุด 5 นาที ถ้า miss
                replace_existing=True,
            )
            logger.info(f"เพิ่ม job: โพสต์ทุกวัน เวลา {time_str}")

    def _is_auto_enabled(self) -> bool:
        """เช็คจาก Firebase RTDB ว่าโหมด AUTO เปิดอยู่ไหม (default: true)"""
        try:
            import firestore_sync as fs
            if not fs._init():
                return True  # fallback ถ้าเชื่อม Firebase ไม่ได้
            val = fs._db.reference("config/auto_mode").get()
            return val is not False  # null/None/true → auto on
        except Exception as e:
            logger.warning(f"[SCHEDULER] เช็ค auto_mode ผิดพลาด ({e}) → ใช้ default AUTO=ON")
            return True

    def _run_workflow(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self._is_auto_enabled():
            logger.info(f"[SCHEDULER] {now} — โหมด MANUAL เปิดอยู่ → ข้ามรอบนี้")
            return
        logger.info(f"[SCHEDULER] เริ่มงาน — {now}")
        try:
            self.workflow.run(trigger="scheduled")
        except Exception as e:
            logger.error(f"[SCHEDULER] เกิดข้อผิดพลาด: {e}")

    def start(self):
        self.setup_jobs()
        print("\n" + "=" * 60)
        print("AUTO POSTER SCHEDULER เริ่มทำงานแล้ว")
        print(f"Niche: {self.config.content_niche}")
        print(f"เวลาโพสต์: {', '.join(self.config.post_times)} (Bangkok)")
        print(f"Facebook: {'เปิด' if self.config.enable_facebook else 'ปิด'}")
        print(f"LINE: {'เปิด' if self.config.enable_line else 'ปิด'}")
        print(f"TikTok: {'เปิด' if self.config.enable_tiktok else 'ปิด'}")
        print("กด Ctrl+C เพื่อหยุด")
        print("=" * 60 + "\n")

        # Signal handlers work only in main thread
        if threading.current_thread() is threading.main_thread():
            def shutdown(signum, frame):
                logger.info("กำลังหยุด scheduler...")
                self.scheduler.shutdown(wait=False)
                sys.exit(0)
            signal.signal(signal.SIGINT, shutdown)
            signal.signal(signal.SIGTERM, shutdown)

        self.scheduler.start()

    def list_jobs(self):
        print("\nรายการ jobs ที่กำหนดไว้:")
        for job in self.scheduler.get_jobs():
            print(f"  - {job.name}: next run = {job.next_run_time}")
