# การแก้ปัญหา Auto-play, YouTube Browser และรีเซ็ตคิวข้อความสด

สถานะ: ปรับปรุง Source Project หลัง Release v0.8.0 (ยังไม่ได้อัปเดต Portable ZIP ที่เผยแพร่)

## Firefox: อ่านอัตโนมัติพักชั่วคราว

- การอ่านผ่าน Firefox อาจเจอ `NotAllowedError` เมื่อยังไม่ได้อนุญาตเล่นเสียงอัตโนมัติ ระบบจะแสดงชื่อข้อผิดพลาดจริงแทนการเหมารวมทุกปัญหาเป็นสิทธิ์ Browser
- เปิดเว็บไซต์จาก Firefox แล้วคลิกไอคอนสิทธิ์/Auto-play ใกล้แถบที่อยู่ของเว็บ เลือกอนุญาตให้เล่นเสียงได้ จากนั้นคลิก **ลองอ่านอัตโนมัติต่อ** หรือ **เล่นเสียง** ด้วยตนเอง
- หากงานเสียงเกิดข้อผิดพลาดจาก TTS/AI Translation, WAV หรือ Audio Scheduler ข้อความจะระบุสาเหตุที่ตรวจพบ ไม่แจ้งว่า Firefox บล็อกเสียงหากยังไม่มีหลักฐาน
- เมื่อ Firefox ปฏิเสธการเล่น WAV ที่สร้างไว้ ระบบพักคิวชั่วคราวโดยคง WAV ที่สร้างแล้วและข้อความรออ่านไว้ ปุ่มลองอ่านต่อใช้ WAV เดิม ไม่สร้างงานซ้ำ
- ข้อความที่พยายามอ่านไม่สำเร็จยังไม่ถูกนับว่าอ่านแล้ว

## YouTube LIVE (Browser) และ Top chat

- เว็บ UI VoxWeaveTTS สามารถเปิดใน **Firefox** ได้ตามปกติ แต่โหมด YouTube LIVE (Browser) ใช้หน้าต่าง **Chromium (Chrome/Edge)** แบบแยกโปรไฟล์เพื่ออ่าน DOM ของ YouTube โดยไม่ได้อ่าน DOM จาก Firefox ของผู้ใช้
- แก้การคลิกเมนูให้เริ่มด้วยปุ่มจริงของ `yt-dropdown-menu` ก่อนเลือก Live chat ที่มองเห็นได้ ตัวเลือกในเมนูที่ยังไม่เปิดจะไม่ถูกคลิกผิด ๆ
- ห้ามแจ้งว่าพร้อมรับ Live chat หรือรับข้อความที่ยังกรองจาก Top chat จนกว่าผลตรวจ DOM จะยืนยัน `chat_mode=live`
- ถ้ายังสลับไม่ได้ โปรแกรมแสดงสถานะ `chat_mode_unconfirmed` และให้ผู้ใช้ตรวจ/เลือก Live chat ด้วยตนเองในหน้าต่าง YouTube Chat-only ที่โปรแกรมเปิดขึ้น พร้อมลองตรวจใหม่โดยไม่จำเป็นต้องหยุดการเชื่อมต่อ
- YouTube สามารถเปลี่ยน DOM หรือจำกัดการแสดง Live Chat โดยแพลตฟอร์มได้ การทดสอบอัตโนมัติใช้ Chromium กับหน้า HTML จำลองเท่านั้น ไม่ใช่หลักฐานว่า LIVE ทุกช่องใช้งานได้จริง

## ปุ่มรีเซ็ตคิวข้อความสด

มีปุ่ม **รีเซ็ตคิวข้อความ** ใน YouTube LIVE (API/Browser), Discord, Discord Client, TikTok LIVE/TikFinity และ TikTok LIVE (Extension)

กดปุ่มนี้เมื่อตามอ่านข้อความไม่ทัน:

1. งาน **หนึ่งข้อความ** ที่กำลังแปล, สร้างเสียง, อ่านเสียง หรือพักรอกดลองอ่านต่อ จะไม่ถูกยกเลิกและจะทำต่อจนจบ
2. ข้อความที่ **ยังไม่ได้เริ่ม** ประมวลผล จะถูกข้าม/นำออกจากคิวรออ่านของ Browser
3. สำหรับช่องทางที่มี Source Manager ฝั่ง Python ระบบจะล้างข้อความที่ยังรอส่งจากเซิร์ฟเวอร์ด้วย (POST `/v1/sources/reset`); ไม่ตัดการเชื่อมต่อ LIVE, ไม่รีเซ็ต cursor/seen IDs และไม่แตะ Source ของโหมดอื่น
4. ข้อความใหม่ที่เข้ามา **หลังรีเซ็ต** จะเข้าแถวต่อท้ายงานที่กำลังทำอยู่ และเริ่มอ่านตามปกติเมื่องานนั้นจบ
5. ไม่ลบไฟล์ Settings, Dictionary, Voice Presets, Model Packages, Credentials หรือประวัติข้อความจากแพลตฟอร์มต้นทาง

API สำหรับผู้พัฒนา: `POST /v1/sources/reset` ด้วย JSON
`{"mode":"youtube_browser","mode_token":"<current owner token>"}`
และ Header `X-VoxWeaveTTS-Intent: reset-live-source-queue`; ผู้เรียกต้องมี Source Owner Token ที่ยังใช้งานได้และไม่สามารถส่งพาธเพื่อลบไฟล์ได้

**หมายเหตุ:** ปุ่มรีเซ็ตคิวใช้กับข้อความ Live ของโหมดที่เลือก ไม่ใช่ปุ่มลบเสียง/ยกเลิกงานทุกโหมดใน Shared Speech Coordinator และไม่ใช้แทนปุ่ม **หยุดเสียง** ที่ตั้งใจยกเลิกเสียงปัจจุบัน

## การทดสอบ

- `tests/mode_inputs_autoplay_smoke.cjs` — Firefox autoplay deny / retry, งาน AI/TTS ล้มเหลว, scheduler cancellation, reset คิวระหว่างอ่าน/ระหว่างเตรียมงานโดยคงงานปัจจุบัน
- `tests/source_feed_smoke.cjs` — รีเซ็ต Client และ Backend Pending โดยยังเชื่อมต่ออยู่
- `tests/test_source_queue_reset.py` — Source Owner, การล้าง Pending แบบเจาะจง, HTTP Intent, คิวใหม่หลังรีเซ็ต
- `tests/test_youtube_browser.py` — ไม่ fallback ไป Top chat แม้รอจนหมดช่วงเริ่มต้น
- `tests/browser_dom_integration_smoke.py` — ใช้ Chromium แบบแยกโปรไฟล์ ทดสอบเปิดเมนูที่ซ่อนอยู่, คลิก Live chat จริง, ยืนยัน label และอ่านข้อความ DOM
