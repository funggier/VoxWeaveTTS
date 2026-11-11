# VoxWeaveTTS — Browser Playback Clock และ OBS Subtitle Overlay

> สถานะ: v0.3.0.dev9 · ระบบกลางที่ **ไม่ผูก TTS Engine** · เฉพาะเครื่อง Local

## หลักการสำคัญ

การสังเคราะห์เสร็จ (Speech Job state = ready) **ไม่ใช่การเล่นเสียงแล้ว**. โมเดล TTS คืน WAV พร้อมข้อมูล Segment และระยะเวลาจาก Audio Samples แต่ **Browser HTMLMediaElement** เป็นตัวรายงานเวลา currentTime ที่กำลังเล่นจริง รวมทั้ง Play, Pause, Resume, Seek และ End

ระบบแบ่งเป็นสามส่วน:

1. Speech Coordinator สร้างไฟล์ WAV และ Timeline ของ Segment แบบไม่ผูก Engine
2. Browser Playback Clock ใช้ currentTime จาก Audio Element ที่กำลังเล่น รายงาน Server ประมาณทุก 250 ms ผ่าน Playback State API
3. OBS Browser Source โหลด Overlay และ Poll State ประมาณทุก 250 ms แล้วแสดง Subtitle ของ Segment ปัจจุบันโดยใช้ textContent (ไม่แทรก HTML)

**ยังไม่มี Word-Level / Phoneme-Level Alignment**: หาก Engine สร้างหนึ่ง Speech Segment ยาวหลายวินาที Subtitle จะแสดงข้อความของทั้ง Segment ในช่วงนั้น ไม่ได้ไฮไลต์ทีละคำ. ความคลาดเคลื่อนจากการ Polling, Network และ Audio Output Latency ยังมีได้ จึงเป็น **Browser-Clock Sync Preview** ไม่ใช่การรับรองว่าตรงระดับเฟรมหรือ Audio Hardware Clock

## การลดความหน่วงด้วย SSE และโหมดแสดงข้อความ

ตั้งแต่ v0.3.0.dev5 หน้า OBS Overlay จะเปิด **EventSource** ไปยัง `GET /v1/playback/stream` เพื่อรับ Subtitle เมื่อสถานะ Browser เปลี่ยน โดยรองรับการเชื่อมต่อซ้ำและ Snapshot ล่าสุดทันที ไม่เก็บประวัติข้อความต้นฉบับหรือ Speech Audio ลง Disk. SSE มีเพดานผู้รับพร้อมกัน 8 ตัว, เปิดค้างต่อรอบไม่เกิน 20 วินาที และใช้ Keepalive ระหว่างไม่มีข้อความ

HTTP Polling ที่ `GET /v1/playback/state` ยังรองรับและจะถูกใช้เป็น Fallback ทุก 1 วินาทีในกรณีที่ SSE ใช้งานไม่ได้ **ความหน่วงรวมยังถูกจำกัดโดยการรายงาน `audio.currentTime` จาก Browser ประมาณทุก 250 ms** และระยะเวลาประมวลผล/แสดงผลที่ OBS

มี URL สองแบบ:

- `http://127.0.0.1:8765/overlay` — **Segment Mode** ใช้ระยะเวลาจากตัวอย่างเสียงที่ Render แล้ว โดยแสดงข้อความทั้ง Segment ไม่ใช่ทีละคำ
- `http://127.0.0.1:8765/overlay?mode=estimated` — **Estimated Mode (ทดลอง)** แบ่งข้อความยาวเป็นช่วงย่อยบนขอบเขตกลุ่มอักขระ Unicode (ไม่แยกวรรณยุกต์ไทยหรือ Emoji ที่อยู่ด้วยกัน) แล้วประมาณเวลาแสดงจากสัดส่วนจำนวนอักขระภายใน Segment นั้น

**โหมด Estimated ไม่ได้วิเคราะห์สัญญาณเสียง** จึงอาจเปลี่ยน Subtitle ก่อนหรือหลังคำที่พูดจริง โดยเฉพาะเมื่อ Engine อ่านคำภาษาไทยช้าหรือเร็วไม่เท่ากัน ห้ามถือว่าเป็น Word/Syllable Forced Alignment จริง หากต้องการความแม่นยำรายคำจะต้องเพิ่ม Aligner ที่ตรวจสอบเชิงพาณิชย์ได้หรือ Engine ที่ส่งเวลา Alignment มาโดยตรง

## Discord Client และ OBS

โหมด Discord Client รับข้อความจากห้องที่เลือกผ่าน Official Local RPC หลังผู้ใช้อนุญาตและแอปมีสิทธิ์ ใช้ Audio Player กับ Overlay เดียวกับโหมด Discord Bot และ Live. เมื่อเปลี่ยนห้องหรือโหมด ข้อความจากห้องเดิมจะหยุดรับและเสียงเก่าจะหยุดตาม Single Active Workspace (ดู [DISCORD_CLIENT_READER_TH.md](DISCORD_CLIENT_READER_TH.md))

## Live/Discord Auto-read กับ OBS (v0.3.0.dev11)

เมื่อผู้ใช้กดเชื่อม Live/Discord Official API และเปิดตัวเลือกอ่านข้อความใหม่อัตโนมัติ โปรแกรมจะสร้างเสียงตามลำดับและรายงานตำแหน่ง Audio Player มายัง OBS Overlay เดิมทีละข้อความ. หากเปลี่ยนโหมด เสียงและ Subtitle ของโหมดเก่าจะหยุดทันที. ระบบยังใช้ Segment/Estimated/Activity/Manual Modes ตามเดิม และไม่ได้รู้จำเวลาคำอัตโนมัติ. ดู [Live Input Guide](LIVE_INPUT_ADAPTERS_TH.md).

## Overlay เดียวสำหรับทุก Workspace

ตั้งแต่ v0.3.0.dev10 มีโหมดที่ส่งสถานะ Playback มายัง Overlay ได้เพียงโหมดเดียว เมื่อเลือกแท็บอื่น Browser จะพักเสียงทันที และ Server จะรีเซ็ต Subtitle เดิมพร้อมออก Token ใหม่. อีกแท็บจะได้ Event ผ่าน SSE/BroadcastChannel ให้หยุดเสียงเก่า. Studio/Reader/Queue/Live/Discord Simulator ใช้ Overlay URL เดิมร่วมกัน (Live/Discord ยังไม่ได้เชื่อมบริการจริง). ดู [Workspace Guide](WORKSPACE_MODES_TH.md).

## แก้ Estimated Subtitle ตัดสระนำหรือตัวสะกดผิด (v0.3.0.dev9)

โหมด `/overlay?mode=estimated` เดิมแบ่งทุกจำนวนกลุ่มอักขระใกล้เคียงกัน ซึ่งไม่ใช่ขอบเขตคำไทย จึงมีกรณีสระนำ เช่น เ แ โ ใ ไ ไปค้างท้าย Subtitle เดิม หรือพยัญชนะตัวสะกดไปขึ้นต้น Subtitle ถัดไป

เปลี่ยนเป็น **แบ่งเฉพาะช่องว่าง/เครื่องหมายคั่นประโยคที่มีอยู่ในข้อความต้นทางจริง** หากข้อความเขียนติดกันโดยไม่มีจุดคั่นเลย จะคง Caption ทั้ง Segment ตามเสียงที่สร้างไว้ ไม่ใช้วิธีเดาตำแหน่งคำจากจำนวนอักขระอีก และ CSS ของ OBS จะให้ Browser จัดบรรทัดภาษาไทยเอง ไม่เปิด overflow-wrap:anywhere

โหมด Estimated ยังคงคำนวณระยะเวลาแสดงของแต่ละช่วงจากสัดส่วนข้อความ ไม่ใช่ Forced Alignment ที่วิเคราะห์เสียงรายคำ จึงอาจเปลี่ยน Subtitle ก่อนหรือหลังคำที่พูดจริงได้ และไม่ได้เพิ่มโมเดลตัดคำหรือ License ใหม่

## Waveform Manual Alignment (v0.3.0.dev8)

ในแผง Manual Alignment เพิ่ม Waveform ที่แสดง WAV จริงและเลือกช่วงได้จาก Canvas เพื่อช่วย Mark เวลา Subtitle อย่างละเอียด แต่ยังต้องตรวจฟังและยืนยัน Cue ก่อนใช้กับ OBS Mode manual; ไม่มี Forced Alignment จากคำพูดโดยอัตโนมัติ ดู [Waveform Editor](WAVEFORM_EDITOR_TH.md)

## Manual Alignment (เพิ่มใน v0.3.0.dev7)

เลือกช่วงข้อความและ Mark เวลาจากไฟล์ WAV ที่ฟังจริงใน Speech Queue จากนั้นบันทึกเป็น Manual Cues ใน Job (ชั่วคราว) แล้วเริ่มเล่นเสียงใหม่ เปิด /overlay?mode=manual ใน OBS เพื่อแสดงเฉพาะช่วงเวลาที่ผู้ใช้ตรวจแก้แล้ว เวลาที่ไม่ได้ระบุ Cue จะไม่แสดงข้อความ ไม่ใช่ Auto Forced Alignment และยังไม่มี Word Recognition อัตโนมัติ ดู [Manual Alignment](MANUAL_ALIGNMENT_TH.md)

## Audio Activity Mode จากสัญญาณเสียง (เพิ่มใน v0.3.0.dev6)

ใช้ `http://127.0.0.1:8765/overlay?mode=activity` เพื่อทดลองซ่อน Subtitle ในช่วงที่ WAV ไม่มีพลังงานเสียง ระบบวิเคราะห์ Mono PCM16 ด้วย RMS จาก Python Standard Library ทำงานหลัง Engine Render เสร็จ และแบ่งข้อมูลได้ด้วยขอบเขต Segment เดิม

**ข้อจำกัด:** ไม่สามารถแยกได้ว่าคำใดกำลังพูด และเสียงที่ไม่ใช่คำพูดก็อาจถูกนับเป็นกิจกรรมเสียงได้ ช่วงเสียงเบามากอาจไม่ถูกตรวจพบ วิธีนี้ไม่ใช่ Forced Alignment รายคำ/พยางค์ ถ้า WAV ไม่รองรับจะกลับไปใช้ Segment Mode โดยรายงาน Fallback ใน API

ดู [Audio Activity Alignment Guide](AUDIO_ALIGNMENT_TH.md)

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

- GET /v1/playback/state?mode=segment|estimated — อ่าน Snapshot ของสถานะผู้เล่น/Subtitle ปัจจุบัน รวม revision/subtitle_precision (ใช้เป็น Fallback)
- GET /v1/playback/stream?mode=segment|estimated — ส่ง Snapshot เมื่อมีการเปลี่ยนสถานะผ่าน SSE: event=playback, id=revision, data=JSON; ส่ง Snapshot ล่าสุดเมื่อเชื่อมต่อใหม่, ไม่มี Log Replay
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
| web/overlay.html | OBS Caption-only Overlay โปร่งใส, SSE และ HTTP Fallback, Text Sanitization |
| web/index.html | เชื่อม Reader และ Queue Audio กับ Media Clock และแสดง Subtitle ระหว่างเล่น |
| src/voxweavetts/subtitle_cues.py | แบ่งข้อความแบบ Estimated Grapheme Windows ที่ไม่อ้างว่าเป็นเสียงรายคำ |
| tests/test_playback_state.py และ tests/test_subtitle_stream.py | Unit/HTTP/SSE Tests โดยไม่ต้องติดตั้งโมเดล |
| tests/playback_clock_smoke.cjs | Node Tests จำลอง HTMLMediaElement play/pause/seek/end |

## ความสามารถและข้อจำกัดในรอบต่อไป

- เพิ่ม Timeline Alignment จาก Engine ที่รองรับ หรือ Forced Aligner ของเราเอง เพื่อ Subtitle ระดับคำ/พยางค์
- เพิ่ม Authenticated Multi-Client Session Ownership และ WebSocket หากขยาย API ไป LAN/Cloud; SSE แบบ Local มีแล้ว
- เพิ่มการกำหนด Style/Position/Subtitles สำหรับ OBS และการตั้งค่าหลาย Scene
- เพิ่ม Audio Device/Playback Service ใน Core หากต้องเล่นเสียงโดยไม่ต้องมี Browser
- รองรับแหล่งข้อความ Live เช่น Discord, YouTube ผ่าน Adapter โดยใช้ Playback API กลาง

โปรเจกต์ยังยึด [Commercial-First License Policy](COMMERCIAL_LICENSE_POLICY_TH.md) เช่นเดิม; การมี Overlay ไม่ได้ให้สิทธิ์นำข้อความหรือเสียงต้นฉบับที่ไม่มีสิทธิ์มาเผยแพร่เชิงพาณิชย์