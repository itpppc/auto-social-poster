"""
Main entry point
รันแบบ: python main.py [--now] [--topic "หัวข้อ"] [--schedule]
"""
import argparse
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from config import Config

# โหลด .env ก่อน
load_dotenv()


def setup_logging(config: Config):
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config.log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Social Media Auto Poster")
    parser.add_argument("--now", action="store_true", help="โพสต์ทันทีเลย")
    parser.add_argument("--topic", type=str, help="กำหนดหัวข้อเอง")
    parser.add_argument("--schedule", action="store_true", help="รันแบบ scheduler อัตโนมัติ")
    parser.add_argument("--niche", type=str, help="เปลี่ยน niche เช่น 'สุขภาพและการออกกำลังกาย'")
    parser.add_argument("--video", type=str, help="path ของ video สำหรับ TikTok")
    args = parser.parse_args()

    config = Config()
    if args.niche:
        config.content_niche = args.niche

    setup_logging(config)

    if args.now or args.topic:
        # โพสต์ทันที
        from workflow import AutoPosterWorkflow
        workflow = AutoPosterWorkflow(config)
        workflow.run(custom_topic=args.topic, video_path=args.video)

    elif args.schedule:
        # รัน scheduler
        from scheduler import AutoPosterScheduler
        scheduler = AutoPosterScheduler(config)
        scheduler.start()

    else:
        parser.print_help()
        print("\nตัวอย่างการใช้งาน:")
        print("  python main.py --now                          # โพสต์ทันที")
        print("  python main.py --topic 'วิธีออมเงิน'          # กำหนดหัวข้อเอง")
        print("  python main.py --schedule                     # รัน scheduler 24/7")
        print("  python main.py --schedule --niche 'สุขภาพ'   # เปลี่ยน niche")


if __name__ == "__main__":
    main()
