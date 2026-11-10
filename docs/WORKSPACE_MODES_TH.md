# VoxWeaveTTS — โหมดการทำงานอิสระและการตั้งค่ากลาง

> v0.3.0.dev10 (Local Preview) · ระบบหลายโหมดและ OBS เดียว · Live/Discord ยังเป็นข้อความทดลอง ไม่ใช่การเชื่อมแพลตฟอร์มจริง

## โครงสร้าง

แต่ละโหมดมีช่องข้อความ ตัวเล่นเสียง งานเสียง และ UI สำหรับงานของตนเอง โดยไม่ใช้ช่องข้อความของโหมดอื่นร่วมกัน แต่ใช้ TTS Engine, Model, Voice, Speed, Gain, Pitch, Bass, Treble, Formant Preserve, Voice Preset, Seed, Rules และ Pronunciations **ส่วนกลาง** ร่วมกัน

ค่าส่วนกลางมีผลกับงานใหม่ ไม่ย้อนเปลี่ยน WAV ที่สร้างไว้แล้ว ข้อความที่พิมพ์อยู่ใน Browser Memory ของโหมดนั้นและไม่เขียนลง Disk โดยอัตโนมัติ

## โหมดที่มี

| โหมด | เครื่องมือ | สถานะ |
|---|---|---|
| สร้างเสียง | ข้อความเฉพาะโหมด, สร้าง/ฟัง/ดาวน์โหลด WAV, Subtitle | ใช้งานได้ |
| อ่านเอกสาร | TXT/Markdown, แก้ข้อความในช่วง, เลือกบท, Bookmark, Auto-next, Subtitle | ใช้งานได้ |
| อ่านไลฟ์สด | ข้อความจำลอง Live Chat, สร้าง WAV, เล่น/หยุด, Subtitle | ทดลอง Local เท่านั้น |
| Discord | ข้อความจำลอง Discord, สร้าง WAV, เล่น/หยุด, Subtitle | ทดลอง Local เท่านั้น |
| คิวและ Subtitle | ข้อความของคิว, WAV Jobs, Waveform และ Manual Alignment JSON | ใช้งานได้ |
| คำอ่านและกฎ | Rules/Pronunciations JSON, ตรวจ/แก้/เพิ่ม/นำเข้า/บันทึก/ทดลองคำอ่าน | ค่ากลาง |
| ตั้งค่ากลาง | Engine/Voice/Speed/DSP/Seed/Voice Preset และบันทึก/โหลดค่า | ค่ากลาง |

การคลิกแท็บในหน้าเว็บจะ **พักเสียงเก่าทันที** และยกเลิกการอ่านอัตโนมัติของ Document Reader โดยไม่ล้างข้อความที่กำลังแก้

## การตั้งค่ากลางที่บันทึกถาวร

1. ไปที่โหมด ตั้งค่ากลาง (หรือปุ่ม ตั้งค่ากลาง ด้านบน)
2. เลือก Engine/Voice และปรับ Speed, Gain, Pitch, Bass, Treble, Formant Preserve
3. กด บันทึก Engine และค่าปรับเสียงเป็นค่ากลาง เพื่อบันทึกลง data/settings/global-voice.json (Git Ignore)
4. ครั้งต่อไปจะโหลดค่ากลางกลับมาใช้; เมื่อเปิดหลายแท็บจะตรวจ Revision ไม่ให้เขียนทับกันโดยเงียบ ๆ
5. Seed, Voice Presets, JSON Rules และ Pronunciations ยังคงใช้ปุ่มบันทึกแบบเดิมในแต่ละส่วน แต่เป็นข้อมูลส่วนกลางของทุกโหมดเช่นกัน

ยังไม่มีการดาวน์โหลดโมเดลจากการเปลี่ยน Engine อัตโนมัติ ถ้าโมเดลที่บันทึกไม่พร้อม โปรแกรมจะเลือก Engine ที่พร้อมแทนโดยแจ้งสถานะ

## สิทธิ์เล่นเสียง: Single Active Workspace

หนึ่ง Local Server มีโหมดที่มีสิทธิ์เล่นเสียงและส่ง Subtitle ไป OBS เพียงโหมดเดียว

- เมื่อสลับแท็บ โปรแกรมจะพัก Audio Element ทั้งหมดและหยุด Auto-Next ภายใน Browser ก่อนรอ HTTP
- POST /v1/modes/activate ออก Token ใหม่สำหรับโหมดนั้น และล้าง Subtitle ของโหมดเก่าทันที
- รายงาน POST /v1/playback/event ต้องส่ง mode และ mode_token ที่เพิ่งได้รับ มิฉะนั้น HTTP 409 และไม่อัปเดต Subtitle
- Browser อื่น/แท็บอื่นจะได้รับ Event ผ่าน Local SSE /v1/modes/stream; มี BroadcastChannel และ Polling ประมาณ 1.2 วินาทีเป็นทางสำรอง
- OBS ใช้ Overlay เดิมช่องเดียวที่ /overlay (หรือระบุ mode=segment, estimated, activity, manual เพื่อเลือกรูปแบบ Subtitle) โดยแสดงเฉพาะ PlaybackState ของโหมดปัจจุบัน
- โหมดใหม่จะ **ไม่เล่นเสียงเองอัตโนมัติ** ต้องสั่ง Play ในโหมดนั้นก่อน
- ถ้ามีการสร้างเสียงด้วย CPU อยู่แล้ว การหยุดเสียง/Subtitle ไม่ได้หมายความว่า CPU Model Inference จะถูกยุติกลางคำทันที; ระบบพยายามยกเลิกงานและทิ้งผลที่มาช้าไม่ให้เล่น

Token นี้ใช้เพื่อจัดการสิทธิ์เล่นใน Local Loopback UI ไม่ใช่การยืนยันตัวตนเพื่อเปิด API สู่ LAN/Internet

## API

- GET /v1/modes/state: สถานะโหมดปัจจุบันและ Revision โดยไม่เปิดเผย Token
- POST /v1/modes/activate: JSON {"mode":"reader"} พร้อม Header X-VoxWeaveTTS-Intent: activate-mode; ตอบ mode_token และ Revision
- GET /v1/modes/stream: SSE event=workspace แจ้งการเปลี่ยนโหมด (ไม่มี Token)
- POST /v1/playback/event: เมื่อเปิด Workspace Controller แล้วต้องมี mode + mode_token ที่ตรงกับโหมดที่ Active
- GET /v1/settings/global-voice: อ่านค่ากลาง Engine/Voice/Speed/DSP ที่บันทึก
- POST /v1/settings/global-voice: JSON {engine_id,voice_id,speed,voice_controls,expected_revision} กับ Header X-VoxWeaveTTS-Intent: save-global-voice; บันทึกแบบ Atomic และป้องกัน Revision ขัดแย้ง

## Live / Discord: งานถัดไป

โหมด Live และ Discord มีช่องข้อความเป็นอิสระพร้อมการสร้างเสียงและ Subtitle ได้แล้ว แต่ยัง **ไม่มีการรับข้อความจาก YouTube Live หรือ Discord จริง** ต้องพัฒนา Input Adapter แยกในอนาคต พร้อม OAuth/Bot Authentication, Reconnection, Deduplication, Rate Limit, Moderation, Queue Priority และกฎการจัดการสิทธิ์/ข้อมูลของแต่ละแพลตฟอร์ม ไม่ควรถือว่าโหมดข้อความทดลองนี้เชื่อมบัญชีสำเร็จแล้ว

ระบบกลางยังใช้ Speech Coordinator ชุดเดียว มี CPU Inference เรียงคิว ไม่ได้แยกโมเดลรันพร้อมกันหลายชุด

## สิ่งที่ยังไม่รองรับ

- การอ่านจาก Live Platform/Discord Bot จริง
- Automatic Word/Syllable Forced Alignment ที่ตรวจ License ครบ
- การบันทึกข้อความ Draft ของแต่ละโหมดข้าม Browser Restart
- การตรวจสิทธิ์แบบ Login สำหรับ API ข้ามเครื่อง
- รับประกันหยุด CPU Inference ที่กำลังรันได้ทันทีเมื่อสลับโหมด

ดู [API](API.md), [Architecture](ARCHITECTURE.md), [Engine-neutral Core](ENGINE_NEUTRAL_CORE_TH.md) และ [Commercial License Policy](COMMERCIAL_LICENSE_POLICY_TH.md).
