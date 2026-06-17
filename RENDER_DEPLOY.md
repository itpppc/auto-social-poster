# 🚀 Render.com Deploy Guide — ฟรี 24/7

## ขั้นที่ 1: Sign up Render.com (1 นาที)

1. เปิด: **https://render.com/register**
2. คลิก **"GitHub"** → login ด้วย account `itpppc`
3. กด **"Authorize Render"**

## ขั้นที่ 2: Connect Repo + Deploy (3 นาที)

1. หน้า Dashboard → คลิก **"New +"** มุมขวาบน
2. เลือก **"Blueprint"**
3. คลิก **"Connect"** ข้าง repo **`auto-social-poster`**
4. ตั้งชื่อ Blueprint: `tonai-poster`
5. กด **"Apply"**

Render จะอ่าน `render.yaml` ที่เตรียมไว้ → สร้าง 2 cron jobs อัตโนมัติ:
- `tonai-auto-poster` — รัน 8 รอบ/วัน
- `tonai-manual-watcher` — poll queue ทุก 5 นาที

## ขั้นที่ 3: ใส่ Environment Variables (5 นาที)

หน้า service จะถาม env vars — copy ค่าจาก `.env` ในเครื่อง:

| Key | Value (จาก .env) |
|-----|------|
| `GEMINI_API_KEY` | (ดูจาก .env ในเครื่อง) |
| `PEXELS_API_KEY` | (ดูจาก .env ในเครื่อง) |
| `FACEBOOK_PAGE_ID` | (ดูจาก .env ในเครื่อง) |
| `FACEBOOK_ACCESS_TOKEN` | (ค่ายาวๆจาก .env) |
| `FACEBOOK_PAGES` | (ค่ายาวๆ 1227 chars จาก .env) |
| `LINE_CHANNEL_ACCESS_TOKEN` | (จาก .env) |
| `CONTENT_NICHE` | อาหารทะเลสด ขนมจีนน้ำยา ... |
| `LINE_CONTENT_NICHE` | อุปกรณ์ IT คอมพิวเตอร์... |

> 💡 เปิด `.env` ในเครื่อง → copy ค่าทีละบรรทัด

## ขั้นที่ 4: Deploy (2 นาที)

1. กด **"Create Services"**
2. รอ Build ~3-5 นาที
3. เห็น **🟢 "Live"** = พร้อมใช้!

## ขั้นที่ 5: ทดสอบ Manual Run

หน้า service `tonai-auto-poster`:
1. คลิก **"Manual Run"** (มุมขวาบน)
2. ดู Logs → ควรเห็น "[OK] FB ..." หลายรอบ
3. เช็ค dashboard https://ton-ai-poster.web.app

## ✅ เสร็จ — ปิดคอมได้แล้ว!

Render.com Free Tier:
- 750 ชม./เดือน คุ้มมาก (เราใช้แค่ ~4 นาที × 8 รอบ + 5 วินาที × 288 รอบ = ~25 นาที/วัน)
- ไม่ต้องบัตรเครดิต
- ทำงาน 24/7 ตลอดไป

## 🆘 ถ้าติดปัญหา

- Build fail: ดู Logs tab ใน Render
- Cron ไม่รัน: ตรวจว่า Schedule ตั้งเป็น UTC (08:00 ไทย = 01:00 UTC)
- Env var ผิด: Settings → Environment → แก้ → กด Manual Run อีกครั้ง
