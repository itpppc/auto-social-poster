# 🔒 Security — สรุปการอุดช่องโหว่

## ช่องโหว่ที่แก้แล้ว ✅

| # | ช่องโหว่ | ความเสี่ยงเดิม | แก้ไข |
|---|----------|----------------|-------|
| 1 | **PIN hash ในหน้าเว็บ** | ใครเปิด source เห็น hash → brute-force offline | ย้ายไป verify ฝั่ง server ผ่าน Firebase Rules — หน้าเว็บไม่มี hash/PIN |
| 2 | **Dashboard API เปิด public ผ่าน tunnel** | คนนอกเรียก `/api/post-now`, อ่าน `/api/log` ได้ | Host Guard — tunnel เข้าได้แค่ `/line/webhook`, route อื่น 403 |
| 3 | **RTDB เขียนได้อิสระ** | ใครก็ push `manual_queue` สั่งโพสได้ | Rules: write ต้องมี `auth === PIN`, validate ขนาด/ชนิด, `config` อ่านไม่ได้ |
| 4 | **Token หลุดใน /api/log** | log มี access token → เห็นผ่าน API | Redact `EAA…/AIza…/act…/Bearer` เป็น `[REDACTED]` |
| 5 | **LINE webhook ไม่จำกัด** | ยิงถล่ม → เผา Gemini quota | Rate limit 30/นาที (global), 8/นาที (ต่อ user), payload ≤512KB |
| 6 | **manual_queue payload ไม่ตรวจ** | ส่ง base64 ใหญ่/topic ยาว → DoS | Validate: image ≤8MB, topic ≤500, platforms ≤10 + PIN auth |
| 7 | **ไม่มี Security headers** | clickjacking, MIME sniffing | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` |
| 8 | **API keys leak ใน git history** | repo public → Pexels/Gemini key เห็นได้ | ลบ `RENDER_DEPLOY.md` จาก history ทุก commit + force push |

## Defense-in-depth (หลายชั้น)

```
Firebase Rules (server)  ← ชั้น 1: ตรวจ PIN/validate
      ↓
manual_watcher._security_check  ← ชั้น 2: ตรวจซ้ำก่อนโพส
      ↓
Host Guard (Flask)  ← ชั้น 3: กัน API หลุดผ่าน tunnel
```

## ⚠️ ต้องทำต่อ (เจ้าของระบบ)

### 1. Rotate Pexels API Key (key เก่า leak แล้วยังใช้ได้)
1. เปิด https://www.pexels.com/api/ → ล็อกอิน
2. กด **"Regenerate"** หรือสร้าง key ใหม่
3. อัปเดตใน `.env` → `PEXELS_API_KEY=<key ใหม่>`
4. Restart service

> Gemini key rotate แล้ว (ตัวเก่าตายไปเอง) · FB/LINE/TikTok tokens ไม่เคย leak — ปลอดภัย

### 2. (แนะนำ) เพิ่ม LINE Channel Secret
`.env` → `LINE_CHANNEL_SECRET=<จาก LINE Console → Basic settings>`
→ เปิด signature verification กัน webhook ปลอม

### 3. เปลี่ยน PIN (ถ้าต้องการ)
PIN ปัจจุบันอยู่ใน `firebase/database.rules.json` (`pin_gate` + `manual_queue`)
เปลี่ยนเลข `3094396` เป็นเลขใหม่ → deploy rules ใหม่ + ตั้ง `DASHBOARD_PIN` ใน `.env`

## หลักการที่ยึด

- **ไม่มี secret ใน client** — PIN/key อยู่ฝั่ง server เท่านั้น
- **ไม่เชื่อ input** — validate ขนาด/ชนิด/สิทธิ์ทุกจุด
- **Least privilege** — RTDB `.read/.write` ปิดเป็นค่าเริ่มต้น เปิดเฉพาะที่จำเป็น
- **Rate limit** — กัน abuse/DoS/เผา quota
