# VoxWeaveTTS — TikTok LIVE (Extension)

ส่วนเสริม Chrome Manifest V3 แบบติดตั้งเอง สำหรับส่งเฉพาะข้อความคอมเมนต์ใหม่จาก **แท็บ TikTok LIVE ที่ผู้ใช้เลือก** ไปยัง VoxWeaveTTS ผ่าน `127.0.0.1` โดยไม่ใช้ CDP หรือเปิด Browser อัตโนมัติ

## ติดตั้ง

1. Chrome → `chrome://extensions`
2. เปิด Developer mode → Load unpacked
3. เลือกโฟลเดอร์ `extensions/tiktok-live-connector` นี้
4. เปิดแท็บ `https://www.tiktok.com/@username/live` ที่คุณมีสิทธิ์เข้าถึง
5. ใน VoxWeaveTTS Tab **TikTok LIVE (Extension)** กรอก URL เดียวกันแล้วกด **สร้างรหัสจับคู่**
6. คลิกไอคอนส่วนเสริมในแท็บ LIVE → Port `8765` → วางรหัส → **เชื่อมต่อแท็บนี้**
7. หยุดโดยกดปุ่มหยุดที่ส่วนเสริมหรือใน VoxWeaveTTS

**หลังแก้ไข/อัปเดตส่วนเสริม:** เปิด `chrome://extensions` กด Reload ที่ส่วนเสริม จากนั้นรีสตาร์ต Backend ใน `Start-Dev.cmd` และจับคู่ใหม่ด้วยรหัสใหม่ รุ่น 0.1.1 เพิ่มตัวอ่าน DOM รูปแบบใหม่และสถานะวินิจฉัยเป็นจำนวน (ไม่เก็บข้อความแชทในส่วนรายงาน)

ถ้าเปิด Chrome Incognito ให้เปิด Allow in Incognito ของส่วนเสริมเองในหน้า Details ส่วนเสริมไม่ต้องการข้อมูลล็อกอินหรือคุกกี้จากเว็บไซต์

**ข้อจำกัด:** ยังไม่มีการทดสอบรับคอมเมนต์ LIVE จริง และ TikTok อาจจำกัดหรือห้ามการดึงข้อมูลอัตโนมัติหากไม่ได้รับอนุญาต ส่วนเสริมไม่ใช่เครื่องมือที่ TikTok อนุมัติ

อ่าน [คู่มือฉบับเต็ม](../../docs/TIKTOK_EXTENSION_READER_TH.md)
