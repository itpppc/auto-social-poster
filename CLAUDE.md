# auto_poster — Social Media Auto Poster

โพสต์ content ที่ AI สร้างลง Facebook / LINE / TikTok อัตโนมัติ (Python, Windows)

## ไฟล์หลัก (แก้เฉพาะที่เกี่ยว)
- `main.py` — entry point (`python main.py --now`, `--topic "..."`)
- `workflow.py` — workflow engine กลาง เชื่อมทุกส่วน
- `config.py` — ค่าตั้ง niche/เวลาโพสต์/API keys (จาก .env)
- `content_generator.py` — สร้าง content ด้วย AI
- `facebook_poster.py` / `line_poster.py` / `tiktok_poster.py` — โพสต์แต่ละแพลตฟอร์ม
- `scheduler.py` — โพสต์ตามตารางเวลา 24/7
- `manual_watcher.py` — เฝ้าดูโพสต์แบบ manual
- `gemini_image_generator.py`, `image_finder.py`, `local_image_pool.py` — ระบบรูปภาพ (ดู IMAGE_SYSTEM.md)
- `dashboard_server.py` — เว็บ dashboard, `firestore_sync.py` — sync Firebase
- `run_service.py` + `install_service.ps1` — รันเป็น Windows service

## ห้ามอ่าน/ห้ามแตะ
`venv/`, `__pycache__/`, `*.log`, `post_logs/`, `my_images/`, `memory/`,
`firebase-service-account.json` (secret!), `cloudflared.exe`

## ระวัง
- ไฟล์นี้อยู่ในโฟลเดอร์ Google Drive sync — ห้ามสร้างไฟล์ขยะ/ไฟล์ชั่วคราวในนี้ (ใช้ scratchpad)
- secrets อยู่ใน `.env` และ `firebase-service-account.json` — ห้าม commit/แสดงค่า
