# VoxWeaveTTS — ระบบสร้างและควบคุมเสียงพูดภาษาไทย

โปรเจกต์โอเพนซอร์สสำหรับระบบ TTS แบบพกพาบน Windows มี Web UI, API, ระบบแก้คำอ่าน, ฟิลเตอร์และแทนคำ, ระบบอ่านแชทสด และ Subtitle ที่ซิงก์กับเสียง

**สถานะปัจจุบัน: Voice Studio Preview v0.2.0.dev5** — มี Local API ข้อความ และ **สร้างเสียง WAV ภาษาไทยจริงผ่าน FastThaiG2P CPU ONNX ได้แล้ว** บนเครื่องที่ติดตั้งโมเดลกับ Runtime แต่ยัง **ไม่มี** การโคลนเสียงของผู้ใช้, ปรับ Pitch/Formant/Emotion, Audio Streaming, ตัวเชื่อม Discord/YouTube, Subtitle Sync หรือ Portable EXE

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
- [แผนการสร้างเสียงส่วนตัวและ Fine-tuning](docs/VOICE_TRAINING_TH.md)

## License
MIT สำหรับซอร์สโค้ด VoxWeaveTTS เท่านั้น เสียงต้นฉบับ โมเดลที่ดาวน์โหลด และโค้ดจากบุคคลที่สามต้องตรวจสิทธิ์ของแต่ละรายการก่อนแจกจ่าย