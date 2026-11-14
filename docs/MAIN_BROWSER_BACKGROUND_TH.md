# VoxWeaveTTS — การอ่านข้อความต่อเนื่องเมื่อหน้าเว็บหลักอยู่เบื้องหลัง

**สถานะ:** โค้ดพัฒนาหลัง v0.7.1 (ยังไม่เผยแพร่ Release ใหม่)

## ปัญหาที่พบจากโค้ดจริง

มีสองจุดที่ทำให้หยุดอ่านเมื่อไม่ได้โฟกัสนาน ๆ:

1. **หน้าต่าง YouTube Chat-only ที่โปรแกรมเปิดแยก** — อาจถูก Chromium ลดการอัปเดตของหน้าเมื่ออยู่เบื้องหลัง; v0.7.1 เพิ่มการเลือก Live chat โดยอัตโนมัติและลด Background Throttling เฉพาะหน้าต่างแยกนี้
2. **หน้าหลักที่ http://127.0.0.1:8765/** — แม้ Python SourceManager จะรับข้อความต่อ แต่ก่อนหน้านี้ JavaScript ใช้ `setInterval` ทุก 1.2 วินาทีเพื่อ POST `/v1/sources/drain`, รอ AI/TTS ด้วย `setTimeout` ทุก 250 มิลลิวินาที, และใช้ Timer สำหรับการรายงานเวลาของ OBS จึงหยุด/หน่วงในแท็บพื้นหลังได้

## การเปลี่ยนแปลงในรอบนี้

### Source Push จาก Python

- เปิด **SSE /v1/sources/stream?mode=all** เพียง **หนึ่งเส้นต่อหน้าโปรแกรมหลัก** หลังผู้ใช้กด Connect ในโหมด YouTube/Discord/Extension ที่รองรับ โดยใช้ Revision แยกแต่ละโหมดเพื่อปลุกเฉพาะช่องที่มีข้อมูลใหม่ (หรือรอบตรวจซ้ำ) ลดโอกาสใช้จำนวนการเชื่อมต่อ HTTP/1.1 ของ Firefox/Chrome จนเต็มเมื่อเปิดหลายช่องพร้อมกัน
- Backend ส่งเฉพาะ **ชื่อโหมด / revision / state / จำนวนข้อความค้าง** แยกตามโหมด ไม่มีข้อความแชท, API Key หรือ Mode Token; การดึงข้อความจริงยังต้องใช้ POST `/v1/sources/drain` ซึ่งต้องมี Owner Token
- Python แจ้งเหตุการณ์เมื่อรับข้อความใหม่หรือสถานะเปลี่ยน; ส่ง snapshot คงสภาพทุก ~6 วินาทีเพื่อตรวจซ้ำหลัง POST ล้มเหลว; SSE เชื่อมต่อใหม่อัตโนมัติเมื่อครบ 20 วินาที
- มีตัวจำกัดผู้รับ SSE และการดึงข้อความค้างด้วยขนาดชุด 10 รายการต่อครั้ง, Backend Pending สูงสุด 40, Local Auto Queue สูงสุด 12, Overflow ถูกทำเครื่องหมายข้ามตามกฎเดิม
- `setInterval` 1.2 วินาทียังคงมีไว้ **เป็นทางเลือกสำรองเท่านั้น** เมื่อ SSE ไม่พร้อม; เมื่อกลับมามองเห็นแท็บ/โฟกัส จะสั่งตรวจคิวทันทีโดยไม่ต้องรอ Timer

### รอ AI/TTS ด้วย Backend Condition

- Live, Document Reader, Studio และ Manual Queue รอผ่าน `GET /v1/jobs/<speech_id>?wait=1` ที่ใช้ Python Condition (รอได้สูงสุด 10 วินาทีต่อ request) ไม่วน `setTimeout` ในหน้าเว็บ
- Server จำกัด concurrent waiters ไม่เกิน 12 และยังคง GET แบบเดิมสำหรับ API ภายนอก
- รุ่นนี้ยังคงใช้ HTMLAudioElement ใน Browser เป็นตัวเล่นเสียงและตัดสินใจอ่านรายการถัดไปเมื่อเสียงจบ รวมทั้งรักษา Serial/Overlap Policy เดิม

### Subtitle / OBS

- เพิ่มรายงานความคืบหน้าจากเหตุการณ์ `HTMLMediaElement.timeupdate` โดยจำกัดไม่ถี่กว่า ~250 มิลลิวินาที; ใช้ Timer เดิมเป็น fallback
- ยังคงยึด **เวลาที่เล่นจริง** (`currentTime`) ไม่อ้างว่าเสียงพร้อมเท่ากับเสียงเล่นแล้ว

## แนวทางทดสอบด้วย YouTube LIVE จริง

1. เปิด VoxWeaveTTS จาก Source/Portable ที่รวมการเปลี่ยนแปลงนี้ (Release v0.7.1 เดิม **ยังไม่มีการแก้หน้าหลัก**)
2. เปิด YouTube LIVE (Browser) ให้สถานะแสดง **Live chat** และ **รับข้อความแบบ Server Push**
3. เริ่มอ่านข้อความโดยกด Connect และเปิด Auto Read ทดสอบเมื่อหน้าเว็บอยู่ด้านหน้า จากนั้นสลับไปโปรแกรมอื่นสักระยะ โดย **ไม่กด Disconnect**
4. ส่งคอมเมนต์ใหม่จากบัญชีทดสอบที่ได้รับอนุญาต ตรวจว่า Source Status จำนวนรับเพิ่ม, มีประวัติข้อความ, มี WAV อ่านอัตโนมัติ และ OBS Subtitle อัปเดตจริง
5. ทดสอบเมื่อหน้าต่าง YouTube Chat-only ถูกบัง และแยกกรณีหน้า VoxWeaveTTS ถูกบัง/ย่อ; หากหยุด ให้ตรวจว่าค้างที่ **รับข้อความ**, **คิว TTS**, **Autoplay** หรือ **สัญญาณ SSE**
6. ถ้าเห็นคำว่า **ใช้ Polling สำรอง** ให้ตรวจการเชื่อมต่อ SSE (หน้า Browser/Network); ตรวจสิทธิ์เล่นเสียงอัตโนมัติสำหรับ `http://127.0.0.1:8765` หากเสียงไม่ออก

## ข้อจำกัดสำคัญ

- **ยังไม่มีผลทดสอบย่อหน้าต่างจริงยาว ๆ กับ YouTube LIVE ที่ได้รับอนุญาต**; การทดลอง Node.js แบบจำลองแท็บ Hidden ยืนยันว่าได้รับข้อความ 23 รายการโดยไม่ต้องเรียก Timer และตรวจการเรียก `timeupdate` โดยไม่ใช้ Timer แล้วเท่านั้น
- ถ้า OS/Browser **freeze/discard/tab unload** จนหยุด JavaScript ทั้งหมด SSE และ Media Events ก็ไม่สามารถบังคับให้ทำงานต่อได้; การแก้ให้เสียงทำงานแม้ Browser ถูก Suspend ทั้งหน้า ต้องย้าย Playback Controller ออกจากเว็บไปเป็น Native/Desktop Player โดยมีการซิงก์ Subtitle ใหม่ (ยังไม่ได้ดำเนินการ)
- ไม่หลบหลีก YouTube API Quota หรือระบบรักษาความปลอดภัย; Browser DOM Reader เป็นช่องทางทดลองและอาจได้รับผลกระทบจากการเปลี่ยนหน้า YouTube
- ไม่เพิ่มการอ่าน Gift/Live event ที่โหมดเดิมยังไม่มีอยู่ และไม่เปลี่ยนค่า Enabled ของ Auto Read / แหล่งข้อมูลโดยอัตโนมัติ

## ไฟล์ที่เกี่ยวข้อง

- `src/voxweavetts/source_manager.py` — Source SSE notify & bounded snapshots
- `src/voxweavetts/server.py` — SSE stream and GET speech job long-poll
- `web/source_feed.js` — EventSource wake, token-scoped drain, fallback and focus recovery
- `web/mode_inputs.js` — long-poll TTS readiness for Live modes
- `web/index.html` — timer-free Document/Studio/Queue readiness
- `web/playback_clock.js` — audio `timeupdate` progress for OBS
- `tests/background_source_push_smoke.cjs`, `tests/playback_clock_background_smoke.cjs`, `tests/main_page_background_syntax_smoke.cjs`
