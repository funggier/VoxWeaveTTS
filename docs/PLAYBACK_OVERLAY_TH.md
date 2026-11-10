# VoxWeaveTTS — Browser Playback Clock และ OBS Subtitle Overlay

> สถานะ: v0.3.0.dev4 · ระบบกลางที่ **ไม่ผูก TTS Engine** · เฉพาะเครื่อง Local

## หลักการสำคัญ

การสังเคราะห์เสร็จ (Speech Job state = ready) **ไม่ใช่การเล่นเสียงแล้ว**. โมเดล TTS คืน WAV พร้อมข้อมูล Segment และระยะเวลาจาก Audio Samples แต่ **Browser HTMLMediaElement** เป็นตัวรายงานเวลา currentTime ที่กำลังเล่นจริง รวมทั้ง Play, Pause, Resume, Seek และ End

ระบบแบ่งเป็นสามส่วน:

1. Speech Coordinator สร้างไฟล์ WAV และ Timeline ของ Segment แบบไม่ผูก Engine
2. Browser Playback Clock ใช้ currentTime จาก Audio Element ที่กำลังเล่น รายงาน Server ประมาณทุก 250 ms ผ่าน Playback State API
3. OBS Browser Source โหลด Overlay และ Poll State ประมาณทุก 250 ms แล้วแสดง Subtitle ของ Segment ปัจจุบันโดยใช้ textContent (ไม่แทรก HTML)

**ยังไม่มี Word-Level / Phoneme-Level Alignment**: หาก Engine สร้างหนึ่ง Speech Segment ยาวหลายวินาที Subtitle จะแสดงข้อความของทั้ง Segment ในช่วงนั้น ไม่ได้ไฮไลต์ทีละคำ. ความคลาดเคลื่อนจากการ Polling, Network และ Audio Output Latency ยังมีได้ จึงเป็น **Browser-Clock Sync Preview** ไม่ใช่การรับรองว่าตรงระดับเฟรมหรือ Audio Hardware Clock

## วิธีใช้บนเครื่อง

1. เปิด Start-Dev.cmd และหน้า http://127.0.0.1:8765/ แล้วเลือก Engine ที่พร้อม
2. ใต้ Document Reader เลือกไฟล์ TXT/Markdown กด สร้างเสียงและอ่านช่วงที่เลือก หรือใช้ส่วน Speech Queue เพื่อสร้าง WAV แล้ว Play ผ่าน Audio Control
3. เปิดหน้า http://127.0.0.1:8765/overlay ในอีกแท็บเพื่อดู Subtitle ที่เลื่อนตามการเล่นจริง
4. ใน OBS เพิ่ม **Browser Source**, URL = http://127.0.0.1:8765/overlay, แนะนำขนาด 1920×1080 (แก้ได้ให้ตรง Scene ของคุณ) พื้นหลังเป็น Transparent และ Subtitle จัดอยู่ด้านล่างจอ
5. OBS ต้องเปิดบนเครื่องที่เข้าถึง Loopback Server นี้ได้: URL 127.0.0.1 อ้างถึงเครื่องที่ OBS รันเอง หากใช้ OBS คนละเครื่องหรือ Server แยกเครื่อง ยังไม่รองรับโดยตรง
6. **เสียงจะออกผ่าน Browser ที่คุณกด Play** ไม่ใช่เสียงจาก OBS Browser Source ของ Overlay; หากต้องการให้เสียงเข้าสตรีม OBS ต้องกำหนด Audio Capture/Output ของ Browser นั้นแยกต่างหาก

### พฤติกรรมเมื่อเล่นเสียง

| เหตุการณ์ | Subtitle / ตำแหน่ง |
|---|---|
| WAV สร้างเสร็จ แต่ยังไม่กด Play | ไม่มี Subtitle จาก Playback |
| กด Play | เริ่ม Session ใหม่ด้วย Audio Timeline ของ WAV ที่สร้างเสร็จ แล้วแสดงคำใน Segment ตาม currentTime |
| ช่วง Silence ที่ไม่มีคำอ่าน | ซ่อน Subtitle เพื่อไม่แสดงข้อมูลคำอ่านส่วนตัว |
| Pause | ซ่อน Subtitle และหยุดการรายงานเวลาแบบต่อเนื่อง |
| Resume | รายงานตำแหน่งปัจจุบันใหม่และแสดง Subtitle |
| Seek | ใช้ currentTime หลังเลื่อนไปตำแหน่งใหม่ ไม่คาดเดาเวลาจากเวลาที่โมเดลสร้าง |
| Audio Ended / Stop | ซ่อน Subtitle และสิ้นสุด Session |
| Browser ปิด/ขาดการเชื่อมต่อ >3 วินาที | Server ทำเครื่องหมาย Stale และซ่อน Subtitle เก่า |

มี **Session ID + Sequence** ป้องกันข้อมูลรายงานล่าช้าจากช่วงก่อนหน้ามาแทนข้อมูลของ Session ใหม่ และจำกัดการมี Subtitle ที่แสดงจากผู้เล่นเครื่องเดียวในเวลาเดียวกัน

## API

- GET /v1/playback/state — อ่าน Snapshot ของสถานะผู้เล่น/Subtitle ปัจจุบัน (ใช้กับ OBS Overlay)
- POST /v1/playback/event — ส่ง Event จาก Browser ซึ่งกำลังเล่นเสียงจริง
- GET /overlay หรือ GET /overlay.html — หน้า Overlay พื้นหลังโปร่งใส
- GET /playback_clock.js — Shared Browser Media Clock Adapter

### ตัวอย่าง Report

    POST /v1/playback/event
    Content-Type: application/json
    X-VoxWeaveTTS-Intent: report-playback

    {
      "session_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "speech_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "event": "progress",
      "sequence": 2,
      "position_ms": 1500
    }

Event ที่รองรับ: start, progress, paused, resumed, seeked, ended, stopped

ข้อกำหนดสำคัญ: Event start ต้องอ้าง speech_id ของ Job ที่ ready จริงและมี audio timeline แล้ว Server ไม่ยอมเริ่ม Playback จาก Job ที่ยังไม่พร้อม ทั้งหมดนี้เป็นสถานะที่ Browser รายงาน ไม่ใช่คำสั่งควบคุมเครื่องเสียงของระบบปฏิบัติการ

Snapshot คืนสถานะ playing, paused, ended, stopped, stale หรือ idle และ Subtitle ที่ผ่าน Text Processor/Filter แล้วเท่านั้น (ไม่ส่ง Original Text หรือ Spoken Replacement สำหรับคำที่ถูกกรอง) พร้อม clock_basis = browser_html_media_current_time_reported

ยังไม่มีการเก็บรายงาน/ข้อความ Subtitle ลง Disk ระบบถูกจำกัดไว้ที่ Local Server; การเปิดบริการให้เครื่องอื่นเข้าถึงต้องออกแบบ Security/Auth ใหม่ก่อน เพราะ Endpoint ควบคุม Playback ไม่ได้มีระบบ Login ในรุ่นนี้

## โค้ดที่เกี่ยวข้อง

| ไฟล์ | บทบาท |
|---|---|
| src/voxweavetts/playback_state.py | ตรวจ Report, เลือก Segment จากเวลาที่รายงาน, ทำ Stale, ป้องกัน Event เก่า |
| src/voxweavetts/server.py | HTTP Playback Endpoints / Static Overlay |
| web/playback_clock.js | Browser Media Clock Adapter สำหรับทุกเสียง |
| web/overlay.html | OBS Caption-only Overlay โปร่งใส, Polling และ Text Sanitization |
| web/index.html | เชื่อม Reader และ Queue Audio กับ Media Clock และแสดง Subtitle ระหว่างเล่น |
| tests/test_playback_state.py | Unit/HTTP Tests โดยไม่ต้องติดตั้งโมเดล |
| tests/playback_clock_smoke.cjs | Node Tests จำลอง HTMLMediaElement play/pause/seek/end |

## ความสามารถและข้อจำกัดในรอบต่อไป

- เพิ่ม Timeline Alignment จาก Engine ที่รองรับ หรือ Forced Aligner ของเราเอง เพื่อ Subtitle ระดับคำ/พยางค์
- เพิ่ม Event Stream (SSE/WebSocket) และ Session Ownership/Auth เมื่อจะเปิด API ให้ LAN/Cloud
- เพิ่มการกำหนด Style/Position/Subtitles สำหรับ OBS และการตั้งค่าหลาย Scene
- เพิ่ม Audio Device/Playback Service ใน Core หากต้องเล่นเสียงโดยไม่ต้องมี Browser
- รองรับแหล่งข้อความ Live เช่น Discord, YouTube ผ่าน Adapter โดยใช้ Playback API กลาง

โปรเจกต์ยังยึด [Commercial-First License Policy](COMMERCIAL_LICENSE_POLICY_TH.md) เช่นเดิม; การมี Overlay ไม่ได้ให้สิทธิ์นำข้อความหรือเสียงต้นฉบับที่ไม่มีสิทธิ์มาเผยแพร่เชิงพาณิชย์
