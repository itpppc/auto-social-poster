# Social Media Auto Poster

ระบบสร้าง content อัตโนมัติและโพสต์ลง Facebook, LINE, TikTok โดยใช้ Claude AI

## โครงสร้างระบบ

```
Claude AI (สร้าง content)
    ↓
Workflow Engine
    ↓
┌─────────────┬─────────────┬─────────────┐
│  Facebook   │    LINE     │   TikTok    │
│  Graph API  │  Notify /   │  Content    │
│             │  Messaging  │  Posting API│
└─────────────┴─────────────┴─────────────┘
```

## ติดตั้ง

```bash
cd F:\ProjectAI\auto_poster
pip install -r requirements.txt
copy .env.example .env
# แก้ไข .env ใส่ API Keys
```

## วิธีใช้

```bash
# โพสต์ทันที
python main.py --now

# กำหนดหัวข้อเอง
python main.py --topic "5 เทคนิคออมเงิน ที่ใช้ได้จริง"

# เปลี่ยน niche
python main.py --now --niche "สุขภาพและการออกกำลังกาย"

# รัน scheduler อัตโนมัติ 24/7 (โพสต์ตามเวลาใน config)
python main.py --schedule
```

## การตั้งเวลา (แก้ใน config.py)

```python
post_times: List[str] = ["08:00", "12:00", "18:00"]
```

## ขั้นตอนรับ API Keys

### Facebook
1. ไป https://developers.facebook.com/ → สร้าง App
2. เพิ่ม "Facebook Login for Business"
3. ขอ Permission: `pages_manage_posts`
4. ใช้ Graph API Explorer สร้าง Page Access Token

### LINE Notify (ง่ายสุด)
1. ไป https://notify-bot.line.me/th/
2. Login → My Page → Generate Token
3. เลือก Group ที่ต้องการส่ง

### LINE Official Account (สำหรับ followers)
1. สร้าง OA ที่ https://manager.line.biz/
2. ไป LINE Developers → สร้าง Messaging API channel
3. Issue Channel Access Token

### TikTok
1. https://developers.tiktok.com/ → สมัครเป็น Developer
2. สร้าง App → ขอ "Content Posting API"
3. รอ approval (~1-2 สัปดาห์)
4. OAuth flow เพื่อได้ Access Token

## รัน 24/7 บน Windows

```bat
# สร้างไฟล์ start.bat
python F:\ProjectAI\auto_poster\main.py --schedule

# ใช้ Task Scheduler ของ Windows
# หรือใช้ NSSM ติดตั้งเป็น Windows Service
```

## รัน 24/7 บน VPS/Linux

```bash
# ใช้ nohup
nohup python main.py --schedule > output.log 2>&1 &

# หรือ systemd service
# หรือ PM2 (Node.js process manager)
pm2 start "python main.py --schedule" --name auto-poster
```
