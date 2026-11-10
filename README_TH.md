# VoxWeaveTTS — ระบบสร้างและควบคุมเสียงพูดภาษาไทย

โปรเจกต์โอเพนซอร์สสำหรับระบบ TTS แบบพกพาบน Windows มี Web UI, API, ระบบแก้คำอ่าน, ฟิลเตอร์และแทนคำ, ระบบอ่านแชทสด และ Subtitle ที่ซิงก์กับเสียง

**สถานะปัจจุบัน: Engine-Neutral Reader Preview v0.3.0.dev11** — มี Local API, Text Processor, Engine Registry, Voice Studio และ **ระบบคิวเตรียมเสียงที่ใช้ร่วมกับ FastThaiG2P/MakHam** พร้อมสร้าง WAV ภาษาไทยจริงได้บนเครื่องที่ติดตั้งโมเดลและ Runtime มี Speed/Gain/Pitch/EQ แบบ Native/DSP แต่ยัง **ไม่มี** Voice Cloning, การฝึกโมเดล, Native Formant/Emotion, Audio Streaming/Hardware Playback Clock, Discord/YouTube, Word-Level Subtitle Sync หรือ Portable EXE

## ฐานระบบกลางที่พัฒนาเพิ่มแล้ว

เพิ่ม **Engine Registry v1** และ **Speech Coordinator** ที่ไม่ผูกกับโมเดล: มีคิวเรียงลำดับ, ID, การป้องกันข้อความซ้ำ, การยกเลิกงาน, เหตุการณ์แบบเวอร์ชัน, WAV ที่ดาวน์โหลดหลังเตรียมเสียงสำเร็จ และหน้าเว็บทดลองคิว โมเดลใหม่ที่ฝึกเองสามารถสร้าง Adapter มาลงทะเบียนด้วย Interface เดียวกัน ไม่ต้องเปลี่ยน Text Processor หรือ API หลัก

ระบบปัจจุบันยัง **ไม่ใช่ Playback Clock, OBS Subtitle Sync, Discord/YouTube Input หรือ Training Engine** และไม่มีการรับรอง License ของโมเดลทุกตัวว่าใช้เชิงพาณิชย์แล้ว

อ่าน [โครง Engine-Neutral Core (ภาษาไทย)](docs/ENGINE_NEUTRAL_CORE_TH.md)

## ตัวแก้กฎคำอ่าน JSON ที่ปรับปรุงแล้ว

ช่อง **Rules** และ **Pronunciations** ที่มีอยู่เดิมมีปุ่ม **จัดรูปแบบ / ตรวจ JSON / บันทึกไฟล์ / นำเข้าไฟล์ / บันทึกในโปรแกรม / โหลดค่าที่บันทึก** และช่อง **เพิ่มรายการเร็ว** เพื่อเพิ่มข้อความที่มีเครื่องหมายคำพูด แบ็กสแลช อักขระไทยหรือ Emoji โดยไม่ต้อง Escape เอง การทดลองอ่านจะใช้กฎเดียวกับ API; เพิ่มการบันทึกถาวรลงโฟลเดอร์ data/filters และ data/dictionaries การโหลดค่าที่เคยบันทึก การนำเข้าไฟล์ JSON และการป้องกันเขียนทับจากอีกแท็บ ส่วนปุ่มบันทึกไฟล์ยังเป็นการดาวน์โหลดแยกกัน อ่าน [คู่มือการตั้งค่าคำอ่าน JSON](docs/PRONUNCIATION_JSON_TH.md)

## Subtitle ตามเวลาที่เสียงเล่นจริงใน Browser + OBS

เพิ่ม Browser Playback Clock ที่ใช้ audio.currentTime ของเสียงซึ่งกำลังเล่นจาก Document Reader หรือ Speech Queue และหน้า http://127.0.0.1:8765/overlay สำหรับ OBS Browser Source แบบพื้นหลังโปร่งใส ใช้ร่วมกับทุก Engine และไม่เริ่มแสดง Subtitle เพียงเพราะสร้าง WAV เสร็จ เมื่อ Pause/Stop/Ended หรือ Browser หยุดรายงานเวลานาน ระบบจะซ่อน Subtitle

**ยังไม่มีการจับเวลาเสียงระดับ Hardware หรือ Subtitle รายคำ/พยางค์**; Overlay ไม่ได้ส่งเสียงให้ OBS โดยตรง อ่าน [คู่มือ Playback และ OBS Overlay](docs/PLAYBACK_OVERLAY_TH.md)

## เชื่อมอ่านข้อความจาก YouTube Live และ Discord (ทดลอง)

โหมด **อ่านไลฟ์สด** และ **Discord** รองรับการรับข้อความใหม่จาก **Official API แบบอ่านอย่างเดียว** แล้ว โดยใช้ YouTube Data API v3 API Key หรือ Discord Bot Token ที่ผู้ใช้เป็นเจ้าของและได้รับอนุญาต กดเชื่อมต่อในโหมดนั้นจึงเริ่มทำงาน คีย์/โทเค็นจะอยู่ในหน่วยความจำชั่วคราว ไม่บันทึกลงดิสก์หรือ Git

เลือกข้อความเพื่อสร้างเสียงด้วยตนเอง หรือเลือก **อ่านข้อความใหม่อัตโนมัติ** ซึ่ง **ปิดไว้เป็นค่าเริ่มต้น** ระบบกรองลิงก์ คำสั่ง Bot และคำที่ไม่ต้องการ พร้อมจำกัดคิวไม่ให้ข้อความเข้ามามากเกิน และหยุดรับ/อ่านเมื่อเปลี่ยนโหมด

**หมายเหตุ:** โค้ด Official API และการทดสอบจำลองพร้อมแล้ว แต่ยังไม่ได้ยืนยันกับ Live/Discord จริงเพราะยังไม่มี Credentials ของผู้ใช้ และเป็น REST Polling ไม่ใช่ Push แบบ Latency ต่ำ คู่มือ: [Live/Discord Inputs](docs/LIVE_INPUT_ADAPTERS_TH.md)

## โหมดอิสระ + ค่ากลาง TTS/คำอ่าน (v0.3.0.dev11)

หน้าตาใหม่แบ่งเป็น **สร้างเสียง, อ่านเอกสาร, ไลฟ์สด, Discord, คิว/Subtitle, คำอ่านและกฎ, ตั้งค่ากลาง** โดยแต่ละโหมดมีข้อความและตัวเล่นของตัวเอง เมื่อเปลี่ยนแท็บเสียงและการอ่านอัตโนมัติของโหมดเดิมจะหยุดทันที มีโหมดที่ได้รับสิทธิ์ส่งเสียงไป OBS ได้เพียงโหมดเดียว แม้เปิดหลายแท็บ

**Engine/Model, Voice, Speed, DSP, Seed, Preset และ Rules/Pronunciations ใช้ค่ากลาง** ไม่ต้องตั้งซ้ำในทุกโหมด สามารถกดบันทึก Engine/Voice/DSP ที่หน้า ตั้งค่ากลาง เพื่อโหลดกลับมาเมื่อเปิดโปรแกรมรอบต่อไป ส่วน JSON คำอ่านและ Seed ใช้การบันทึกกลางเดิม

**โหมด Live และ Discord ยังคงให้ทดลองพิมพ์ข้อความจำลองได้** และสามารถเชื่อม Official API แบบอ่านอย่างเดียวเมื่อผู้ใช้ตั้งค่า Credentials เอง (ยังไม่ได้ทดสอบกับบัญชีจริง) ดู [คู่มือโหมดและค่ากลาง](docs/WORKSPACE_MODES_TH.md)

## ปรับปรุงการตัด Subtitle และช่วงอ่านภาษาไทย

แก้อาการที่สระนำ เช่น เ แ โ ใ ไ หรือตัวสะกดถูกตัดไปอยู่คนละ Subtitle: **Estimated Mode** จะเลือกแบ่งเฉพาะช่องว่าง/เครื่องหมายคั่นที่เห็นได้ชัด หากประโยคไทยยาวโดยไม่มีจุดแบ่ง จะใช้ข้อความทั้ง Segment เดิมแทนการเดาคำ; Overlay ใช้การขึ้นบรรทัดตามภาษาใน Browser ไม่บังคับตัดกลางคำด้วย CSS

Document Reader ก็ให้ความสำคัญกับจุดคั่นตามธรรมชาติมากขึ้น หากจำเป็นต้องตัดข้อความไทยติดกันให้สั้นตามขนาด Chunk จะมีคำเตือนว่าตำแหน่งนั้นเป็นเพียงการแบ่งแบบประมาณ ไม่รับรองว่าเป็นขอบเขตคำจริง

**หมายเหตุ:** เปลี่ยนอัลกอริทึมแบ่ง Chunk จึงปรับ Version ของ Document ID เพื่อป้องกันการอ่านต่อผิดตำแหน่ง Bookmark ของเอกสารเก่าจะต้องเลือกตำแหน่งและบันทึกใหม่อีกครั้ง (ข้อมูลเดิมไม่ถูกลบ) ดู [คู่มือ Document Reader](docs/DOCUMENT_READER_TH.md) และ [Subtitle Overlay](docs/PLAYBACK_OVERLAY_TH.md)

## Waveform Editor — มองเห็นคลื่นเสียงและกำหนดช่วงเวลาได้ละเอียดขึ้น

เพิ่ม Waveform จาก PCM16 WAV จริงที่ Speech Queue สร้างแล้วในแผง Manual Alignment รองรับซูม 1–32 เท่า เลื่อนดูช่วงอื่น คลิกเลื่อน Audio Player ลากคลื่นเพื่อกำหนดเวลาเริ่ม–จบ และกดลูกศรขยับเวลา 25ms (Shift = 5ms). Canvas ปรับตามขนาดหน้าจอ/HiDPI ไม่ใช้โมเดลหรือไลบรารีภายนอก และยังบันทึก Cue ตามขั้นตอนเดิมเท่านั้น

Waveform เป็นเครื่องมือช่วย **ตรวจฟังและ Mark เวลาเอง** ไม่ใช่ระบบรู้จำคำจากเสียงโดย AI ดู [คู่มือ Waveform Editor](docs/WAVEFORM_EDITOR_TH.md)

## Manual Alignment — จับเวลา Subtitle รายคำ/วลีจากเสียงที่ฟังเอง

เพิ่มส่วน Manual Alignment ใต้ Speech Queue: เลือกข้อความจาก Segment, จับจุดเริ่ม–จบจากเวลาเล่น WAV จริง, แก้ JSON, บันทึก Cue แบบชั่วคราวใน Speech Job, นำเข้า/ส่งออกไฟล์ JSON และประเมินความคลาดเคลื่อนเทียบ Reference Timecodes ได้ จากนั้นเปิด http://127.0.0.1:8765/overlay?mode=manual ใน OBS

ระบบนี้ใช้ข้อมูลจากเสียงที่คุณฟังและตรวจแก้ **ไม่ได้ตรวจจับคำอัตโนมัติ** ไม่มีโมเดล/ชุดข้อมูลภายนอกหรือสิทธิ์เชิงพาณิชย์เพิ่มเติม และไม่เก็บ Cue ถาวรลง Server โดยอัตโนมัติ ดู [คู่มือ Manual Alignment](docs/MANUAL_ALIGNMENT_TH.md)

## Audio Activity — Subtitle จากช่วงเสียงจริง (ทดลอง)

เพิ่มโมดูลวิเคราะห์พลังงานสัญญาณ PCM จาก WAV ที่สร้างแล้ว โดยไม่ต้องมีโมเดลภายนอกหรือ Dependencies ใหม่ ใช้กับ TTS Engine ได้ทุกตัว และแยกออกจากตัว Engine ผ่าน AudioAlignmentProvider

เปิด <http://127.0.0.1:8765/overlay?mode=activity> เพื่อทดลอง Subtitle ที่ซ่อนในช่วงเงียบซึ่งตรวจพบจาก Waveform จริง **นี่ไม่ใช่ Forced Alignment ระดับคำหรือพยางค์** การระบุว่าคำไหนกำลังออกเสียงยังต้องอาศัยโมเดลหรือ Aligner เพิ่มในอนาคต ซึ่งจะต้องตรวจสิทธิ์เชิงพาณิชย์ก่อน ดู [คู่มือ Audio Alignment](docs/AUDIO_ALIGNMENT_TH.md)

## OBS Subtitle แบบ SSE และช่วงข้อความที่ประมาณเวลา (ทดลอง)

เพิ่ม **Server-Sent Events (SSE)** ส่งสถานะเสียงที่เปลี่ยนไปยัง Overlay ทันทีที่ Browser รายงาน โดยไม่ต้องรอรอบ HTTP Polling 250 ms แบบเดิม เมื่อ SSE ใช้ไม่ได้ Overlay จะกลับไปใช้ HTTP Polling ทุก 1 วินาทีอัตโนมัติ

- `http://127.0.0.1:8765/overlay` — แสดง Subtitle ตามขอบเขต Segment ที่สร้าง WAV จริง (ค่าเริ่มต้น)
- `http://127.0.0.1:8765/overlay?mode=estimated` — แบ่งข้อความเป็นช่วงย่อยที่ไม่ตัดวรรณยุกต์ไทย/Emoji แต่ **เวลาเป็นค่าประมาณตามจำนวนกลุ่มอักขระ ไม่ใช่การจับเสียงรายคำจริง** แนะนำให้ทดลองก่อนใช้งานจริง

ทั้งสองรูปแบบใช้ได้กับทุก Engine และยังไม่ต้องติดตั้งโมเดลเพิ่ม ดู [คู่มือ Subtitle/OBS](docs/PLAYBACK_OVERLAY_TH.md)

## บันทึกตำแหน่งอ่านค้างและอ่านทีละช่วง

ในแผง **นำเข้าเอกสาร TXT/Markdown** สามารถกด **จดตำแหน่งช่วงนี้**, **ไปยังตำแหน่งที่อ่านค้าง**, **ล้างตำแหน่งที่จำ** และ **สร้างเสียงและอ่านช่วงที่เลือก** ได้แล้ว มีปุ่มพัก/เล่นต่อ หยุด และตัวเลือกอ่านช่วงถัดไปอัตโนมัติ โดยจะสร้างเสียงทีละช่วง ไม่สร้างทั้งเล่มล่วงหน้า

ตำแหน่งอ่านบันทึกใน `data/reading/positions.json` ภายในโปรเจกต์ (Git Ignore) เก็บเพียง Hash ของเนื้อหาและหมายเลขช่วง ไม่บันทึกข้อความนิยาย; เมื่อเล่นเสียงใน Browser จบหนึ่งช่วงจึงค่อยบันทึกว่าช่วงถัดไปเป็นจุดอ่านต่อ หาก Browser ไม่อนุญาต Auto-play ให้กด Play ในแถบเสียงเอง **ยังไม่มี Audio Playback Clock ที่ต่อ OBS, ข้อความ Subtitle แบบ Live หรือ Playback ข้ามอุปกรณ์**

## ระบบนำเข้า TXT / Markdown ที่เพิ่มแล้ว

เพิ่ม **Document Reader** สำหรับเลือกไฟล์ .txt/.md จากเครื่อง แบ่งบท/ตอน และช่วงข้อความผ่าน Core เดียวกันได้ โดยไม่ต้องมี TTS Engine ในขั้นจัดเอกสาร รองรับ UTF-8 หรือ Thai Windows-874 มีปุ่มส่งช่วงที่เลือกเข้าคิวเตรียมเสียงพร้อมกฎการอ่านเดิม **ยังไม่อ่านทั้งเล่มต่อเนื่องหรือบันทึก Resume Position ข้าม Session** ดู [รายละเอียด Document Reader](docs/DOCUMENT_READER_TH.md)

## ข้อกำหนดที่ต้องรักษา
1. ปรับเสียงได้: ความเร็ว, ระดับเสียง, Formant, ความกังวาน, อารมณ์, เว้นจังหวะ (ขึ้นกับความสามารถของ TTS รุ่นนั้น)
2. เลือกเสียงอ้างอิงของผู้ใช้ หรือเพิ่ม Voice Profile ได้โดยไม่เผยแพร่ไฟล์ส่วนตัว
3. พจนานุกรมการออกเสียงภาษาไทย แยกคำอ่านออกจากคำสะกดบน Subtitle เช่น อมตะ → อะ มะ ตะ
4. กรองและแทนคำแบบตั้งค่าได้: ไม่อ่าน, เงียบตามเวลา, แทนคำพูด, หรือแทนเฉพาะ Subtitle
5. รองรับนิยาย, ไฟล์ .txt/.md, Discord และ YouTube Live/Comments ผ่าน Input Adapters
6. Audio Playback Coordinator ส่ง speech.queued/started/segment/completed/cancelled พร้อมตำแหน่งเวลาและ ID
7. Subtitle สำหรับ OBS Browser Source และ Consumer อื่น ผ่าน Event API ที่ไม่จำเป็นต้องผูกกับ OBS
8. API แบบ Local-first: ค่าเริ่มต้นฟังเฉพาะ 127.0.0.1, หากจะเปิดให้เครื่องอื่นเข้าถึงต้องเพิ่ม authentication
9. Portable: ย้ายโฟลเดอร์ได้ทั้งชุด; เก็บ Model/Cache/Config ภายในโฟลเดอร์หลัก
10. โมดูลต่างๆ ต้องทดสอบแยกกันได้และเปลี่ยน TTS Engine ได้

## ทดลองเสียงภาษาไทยบนเครื่องจริง

1. รัน `powershell -ExecutionPolicy Bypass -File scripts/Install-ThaiEngine.ps1` เพื่อสร้าง `.venv` และติดตั้งโมเดลไทยไว้ในโฟลเดอร์โปรเจกต์ (ต้องมี `uv`, `gh` และอินเทอร์เน็ตในครั้งแรก)
2. ดับเบิลคลิก `Start-Dev.cmd` และเปิด http://127.0.0.1:8765
3. เลือก **Engine** ระหว่าง FastThaiG2P และ MakHam Paradee, ปรับ Speed/Gain/Pitch/Bass/Treble ด้วย Slider หรือช่องตัวเลข (มีการตรวจค่าตามช่วงที่กำหนด) กด **สร้างเสียง WAV** และฟังผลจริง; เมื่ออ่าน `55555` เพี้ยน ให้ทดลองเปรียบเทียบ Engine และปรับกฎ `Rules/Pronunciations` ด้วยตนเอง (แผงเลือกคำอ่านเสียงหัวเราะเฉพาะกิจถูกถอดออกแล้ว) ไม่ใช่เปลี่ยน Seed
4. สามารถตั้งชื่อและบันทึก **Voice Preset** แล้วโหลดกลับมาใช้งานได้ เก็บไว้ใน `data/presets/voice-presets.json` ภายในโปรเจกต์
5. ใช้ `scripts/Generate-ThaiSample.ps1` เพื่อสร้าง WAV จาก API หรือใช้ `scripts/Smoke-VoiceStudio.ps1` เพื่อทดสอบ Engine ทั้งสอง
6. ใช้ `Test-Dev.cmd` ทดสอบ
7. ทดลอง **นำเข้าเอกสาร TXT / Markdown** เลือก Encoding, Chapter และ Chunk แล้วนำช่วงไปแก้ไขในช่องข้อความหรือส่งเข้าคิวเสียงได้
8. ลองส่วน **คิวเตรียมเสียง (Engine-independent)** บนหน้าเว็บ เพื่อเข้าคิว, ดูสถานะ, ยกเลิก และดาวน์โหลด WAV เมื่อ Ready โดยไม่ผูกกับ Engine ตัวใดตัวหนึ่ง

กฎตัวอย่าง `match_mode: "five_run"` รองรับเลข 5 ตั้งแต่ 3 ตัวขึ้นไปในแชท เช่น `555`, `55555`, `55555555` โดยอ่านเป็น `ฮ่า ฮ่า ฮ่า` แต่แสดงเลขเดิมบน Subtitle และไม่นำรูปแบบตัวเลขอย่าง `5,55555` หรือ `55555.50` มาอ่านเป็นเสียงหัวเราะ

ยังเป็น Development Prototype ไม่ใช่ Portable EXE และยังไม่รองรับการฝึก/โคลนเสียงของเจ้าของโปรเจกต์ ค่าปรับ Pitch/Bass/Treble ต้องมี FFmpeg ที่รองรับ Rubber Band ส่วนการเปลี่ยน Formant โดยอิสระและ Emotion ยังไม่รองรับ

## ที่มาและแผนพัฒนา

- [ที่มา ปัญหาที่ต้องการแก้ และเหตุผลของการออกแบบ](docs/PROJECT_VISION_TH.md)
- [แผนพัฒนาแบบละเอียดพร้อมขั้นตอน ทดสอบ และเกณฑ์ยอมรับ](docs/DEVELOPMENT_PLAN_TH.md)
- [ตารางข้อกำหนดและสถานะของฟีเจอร์](docs/REQUIREMENTS_TH.md)

## เอกสารเทคนิค

- [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Portable](docs/PORTABLE.md)
- [Roadmap (checklist)](docs/ROADMAP.md) · [Security](docs/SECURITY.md)
- [M1 — การเชื่อม TTS Engine ไทยและผลทดลองเสียงจริง](docs/M1_AUDIO_TH.md)
- [Voice Studio — การเลือก Engine และค่าปรับเสียงละเอียด](docs/VOICE_STUDIO_TH.md)
- [โครงระบบ Engine-Neutral Core, Registry, Queue และ Adapter v1](docs/ENGINE_NEUTRAL_CORE_TH.md)
- [Document Reader — นำเข้า TXT/Markdown แบ่งบท/ช่วงแบบไม่ผูก Engine](docs/DOCUMENT_READER_TH.md)
- [แผนการสร้างเสียงส่วนตัวและ Fine-tuning](docs/VOICE_TRAINING_TH.md)

## Commercial-First License Policy

**กำหนดให้โปรเจกต์คัดเลือก Engine โดยเน้นการใช้เชิงพาณิชย์ก่อน** และไม่รับรองว่า Model/Voicepack ใดพร้อมนำไปแพ็กแจกหรือขายจนกว่าจะตรวจสิทธิ์ของไฟล์และ Dependency ที่ใช้จริงครบถ้วน โดยเฉพาะเสียงและข้อมูลฝึก

- [นโยบายการใช้เชิงพาณิชย์และรายการ Engine ที่อนุมัติ/พักไว้](docs/COMMERCIAL_LICENSE_POLICY_TH.md)
- สำหรับการฝึกเสียงเองให้ใช้ไฟล์เสียงที่มีสิทธิ์/ได้รับอนุญาตเท่านั้น
- โมเดลที่มี NC หรือ License ไม่ชัดจะไม่ถูกนำไปใส่ในชุด Commercial/Portable Distribution หลัก
- SiangTTS (CC BY-SA) **ใช้เชิงพาณิชย์ได้ตามเงื่อนไข** แต่พักไว้เพื่อลดภาระ ShareAlike/การปฏิบัติตาม License
- VoxCPM2 (Apache 2.0 สำหรับ code+weights) เป็นตัวเลือกหลักที่จะประเมินสำหรับ Voice Cloning; ไม่ถือว่าผ่านครบทุก Dependency โดยอัตโนมัติ

## License
MIT สำหรับซอร์สโค้ด VoxWeaveTTS เท่านั้น เสียงต้นฉบับ โมเดลที่ดาวน์โหลด และโค้ดจากบุคคลที่สามต้องตรวจสิทธิ์ของแต่ละรายการก่อนแจกจ่าย