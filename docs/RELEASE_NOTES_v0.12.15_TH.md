# VoxWeaveTTS v0.12.15 — แก้รับข้อความ VoxWeaveSTT (API) จริง

## แก้ไข

- แก้ตัวตรวจ `transcript.final` ของ VoxWeaveSTT API: ค่า `active.id` ใช้ระบุ **งานถอดเสียง** ขณะที่ `event.session_id` ใช้ระบุ **การจับเสียง** ซึ่งเป็นคนละค่า การเทียบให้เท่ากันทำให้โหมด STT ปฏิเสธข้อความทั้งหมดและขึ้น `STT transcript event violates contract`
- ตรวจข้อมูล `session_id` ที่มากับ event โดยไม่เปรียบกับ job ID และยังคง validate sequence, segment_id และ revision; อ่านเฉพาะ Final ใหม่ตาม cursor
- เพิ่มการทดสอบที่ตั้ง job session ID และ capture session ID ให้แตกต่างกันเหมือนผลลัพธ์จาก STT จริง พร้อมตรวจ API ของ STT ที่เปิดใช้งานจริงก่อนเผยแพร่
- ปรับคำอธิบายหน้า VoxWeaveSTT (API) ให้แยกชัดเจน: **STT/TTS อยู่เครื่องเดียวกันไม่ต้องใช้ PIN หรือ Fingerprint** แม้ควบคุม TTS ผ่านหน้าเว็บจากเครื่องอื่น
- สำหรับ STT ที่รันต่างเครื่อง: เปิด **VoxWeaveSTT Server → API / ตั้งค่า → เปิด HTTPS LAN (ต้องยืนยัน)** แล้วคัดลอก SHA-256 ผ่านหน้าเว็บ STT v0.1.1 ขึ้นไปใน **ตั้งค่า / API → ข้อมูลเชื่อมต่อและใบรับรอง** หรือจากหน้าต่างจับคู่ (ไม่ใช่ SHA256SUMS ของ ZIP)

## ดาวน์โหลด

- `VoxWeaveTTS-v0.12.15-portable.zip` — Server/Core พร้อมแก้ STT
- `VoxWeaveTTS-Client-v0.12.15-portable.zip` — Remote Client แยก (ความสามารถเดิม)
- `SHA256SUMS-v0.12.15.txt` — ค่า SHA-256 ของสองไฟล์ ZIP

## วิธีใช้งานหลังอัปเดต

1. ปิด **VoxWeaveTTS v0.12.14 Server** ที่กำลังรัน (อย่าปิด VoxWeaveSTT)
2. แตก ZIP ของ v0.12.15 ไปยังโฟลเดอร์แยก แล้วเปิด VoxWeaveTTS Server ใหม่ตามปกติ
3. โหมด **VoxWeaveSTT (API)**: IP `127.0.0.1`, Port `8766` และ **ไม่เปิด** ใช้ HTTPS LAN สำหรับ STT/TTS ในเครื่องเดียวกัน
4. กด **เชื่อมต่อ STT** แล้วรอข้อความ Final ใหม่จาก STT; ข้อความเก่าก่อนกดเชื่อมต่อจะไม่ถูกนำมาอ่าน

หมายเหตุ: หาก VoxWeaveSTT บันทึกเสียงจาก Desktop Loopback เครื่องเดียวกับเสียงออกของ TTS ให้ระวังวงจรจับเสียงตัวเองซ้ำ

ดู [คู่มือ STT API](STT_API_MODE_TH.md) และ [บันทึก v0.12.14](RELEASE_NOTES_v0.12.14_TH.md)
