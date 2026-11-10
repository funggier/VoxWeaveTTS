# VoxWeaveTTS — ตารางข้อกำหนด (Requirement Traceability)

> อ้างอิง: การสนทนาออกแบบโปรแกรมและเอกสาร [PROJECT_VISION_TH.md](PROJECT_VISION_TH.md)  
> สถานะ: 10 พฤศจิกายน 2026; ค่า **Foundation** หมายถึงมีบางส่วนจริง ไม่ถือว่าความสามารถปลายทางเสร็จ

## วิธีใช้ตาราง
- **Done (foundation):** พัฒนาและทดสอบพฤติกรรมในระดับที่ระบุแล้ว
- **Partial:** มีฐานรองรับแต่ยังใช้จริงครบไม่ได้
- **Planned:** เป็นข้อกำหนดที่ตั้งใจพัฒนา ยังไม่มีการรับรองว่าทำงานได้
- ลำดับ M0–M6 เชื่อมกับ [DEVELOPMENT_PLAN_TH.md](DEVELOPMENT_PLAN_TH.md)

| ID | ความต้องการ | โมดูลที่รับผิดชอบ | ระยะ | สถานะและขอบเขตจริง | หลักฐานยอมรับเมื่อเสร็จ |
|---|---|---|---|---|---|
| R-001 | อ่านภาษาไทยเป็นเสียงจริง | VoiceEngine | M1 | Partial: สร้าง WAV ไทย CPU ได้แล้ว ยังไม่ตรวจฟังคำอ่าน | สร้าง WAV ได้และตรวจฟังจริง |
| R-002 | ใช้เสียงตัวอย่างของผู้ใช้ | VoiceProfiles + Engine | M1–M2 | Planned | เพิ่ม/เลือกโปรไฟล์และฟังได้ โดยไม่เผยแพร่เสียง |
| R-003 | แก้คำอ่าน เช่น อมตะ/เซียน | Thai Text Processor / Pronunciation | M0–M2 | Partial: Dictionary Hint เท่านั้น | ตรวจฟังแล้วออกเสียงถูกจริง |
| R-004 | ปรับ Speed, Pitch, Formant, EQ, Emotion, Pause | VoiceStudio + DSP | M2 | Partial: Speed/Gain/Pitch/Bass/Treble + Formant Preserve ใช้ได้; Native Emotion/Formant ยังไม่รองรับ | ทดลอง A/B และบันทึก Preset; Engine แจ้ง Capability |
| R-005 | กรองคำ ไม่ให้อ่าน | ContentFilter | M0–M1 | Partial: Text Plan | เสียงจริงไม่มีคำที่ซ่อน |
| R-006 | Mask คำใน Subtitle เป็น *** | ContentFilter + Subtitle | M0–M5 | Partial: Display Text เท่านั้น | Overlay ไม่แสดงคำต้นฉบับ |
| R-007 | เว้นเงียบก่อนอ่านต่อ | SpeechPlan + Audio Timeline | M0–M1 | Done: มี Silence เป็น PCM จริงใน WAV ทดสอบ 400ms | Audio มี Silence ตามเวลา |
| R-008 | แทนคำที่พูดโดย Subtitle ยังแสดงคำเดิม | ContentFilter | M0–M1 | Done (foundation text only) | Text Plan และเสียงจริงหลัง M1 |
| R-009 | แทนคำทั้งเสียงและ Subtitle | ContentFilter | M0–M1 | Done (foundation text only) | เทสต์ API และการเล่นจริง |
| R-010 | กฎแยกทุกเรื่อง/ต่อเรื่อง/ต่อแหล่งที่มา | RuleStore | M0–M2 | Partial: กฎแยกตาม Source ได้ | Import/Export/Scope และบันทึกค่า |
| R-011 | อ่านนิยาย/บทความจาก TXT/MD | NovelReader | M2 | Planned | โหลดหลายบท, Pause/Resume, คำอ่านเฉพาะเรื่อง |
| R-012 | อ่าน Discord Chat | DiscordAdapter | M4 | Planned | รับแชทที่ได้รับอนุญาตแล้วเข้าคิวได้ |
| R-013 | อ่าน YouTube Live Chat/Comments | YouTubeAdapter | M4 | Planned | Live + Comments แยกวิธีดึงและไม่อ่านซ้ำ |
| R-014 | API ใช้งานจากโปรแกรมอื่น | HTTP API | M0–M4 | Partial: Text API และ WAV /v1/speech ใช้ได้แล้ว ยังไม่มี Event/Streaming | External Client ส่งข้อความและได้รับ Speech/Event |
| R-015 | จัดคิวข้อความสด/ตัดคำ/กรอง Spam | MessageQueue | M3–M4 | Planned | Burst, TTL, Dedup, Priority Test |
| R-016 | ส่ง Speech Event พร้อมข้อมูล Subtitle | EventBus + Coordinator | M3–M5 | Planned | มี ID, Timestamp, Status, Reconnect Snapshot |
| R-017 | Subtitle แสดงตามเสียงจริงบน OBS | Overlay + Playback Clock | M5 | Planned | Full Message Start/Stop ตาม Audio; Cancel ล้างจอ |
| R-018 | Segment/Word Karaoke Highlight | Alignment + Overlay | M5 | Planned | Word Timestamp จาก Audio จริง |
| R-019 | รองรับ Consumer อื่น เช่น Unity/AI | Event API | M3–M5 | Planned | ตัวอย่าง Client แยกจาก OBS |
| R-020 | โปรแกรม Windows Portable ไม่ต้องติดตั้ง Python | PortableBuilder | M6 | Planned | ZIP รันบน Windows สะอาด |
| R-021 | โมเดล/แคช/เสียง/ข้อมูลไม่ลง GitHub | Data Isolation + Security | ทุกระยะ | Partial: .gitignore และข้อกำหนด | Audit ป้องกันข้อมูลรั่ว |
| R-022 | ย้ายโฟลเดอร์/ไดรฟ์ไม่เสียค่า | Portable Paths | ทุกระยะ / M6 | Planned | Rename/Move Test, เก็บค่าเดิม |
| R-023 | License โค้ด MIT + ตรวจสิทธิ์โมเดล | Legal/Release | M0/M6 | Partial: Code MIT | Model License Manifest ก่อน Release |
| R-024 | หน้าตาโปรแกรมใช้งานบนจอปกติ ปรับขนาดได้ | Web UI | M0–M2 | Partial: Preview Responsive | ทดสอบ Resolution/Scaling |
| R-025 | Profile เสียงและเครื่องมือจูนใช้ได้กับหลาย Engine | Engine Adapter + VoiceStudio | M1–M2 | Partial: เลือก 2 CPU Engines และใช้ Preset/DSP ชุดเดียวกันได้ แต่ยังไม่มี Voice Cloning | Swap Backend โดยไม่แก้ Dictionary/Queue |
| R-026 | ปิดเฉพาะ API Server โดยไม่ต้องเปิดหน้าจอ | Server Launcher | M6 | Partial: CLI Dev Server | เปิด API ได้จาก Portable Launcher |
| R-027 | ระบบอัปเดตโดยไม่ทับข้อมูลผู้ใช้ | Upgrade/Migration | M6 | Planned | Backup, Upgrade, Rollback/Recovery Test |

## สิ่งที่ยึดเป็นเกณฑ์สำคัญ

**คำอ่านภาษาไทย:** การแทนข้อความเป็นคำอ่านไม่ได้ยืนยันว่าระดับเสียงและวรรณยุกต์จริงถูก ต้องฟัง Audio เพื่อวัดผล  
**ข้อมูลที่กรอง:** ห้ามส่งคำต้นฉบับที่ถูกซ่อนออกไปใน Subtitle/Event/Log เผยแพร่โดยไม่ตั้งใจ  
**เวลา Subtitle:** ใช้ Audio Playback Clock เท่านั้น ไม่ใช้เวลาโพสต์แชท  
**Portable:** แตก ZIP ต้องใช้งานได้บนเครื่องที่ไม่มี Python; การต้องมี Driver GPU เป็นเงื่อนไขต่างหาก  
**ความจริงของสถานะ:** API/Text Preview ใน M0 ไม่เท่ากับระบบ TTS ที่สร้างเสียงแล้ว

## งานที่จะเริ่มก่อน

Next priority: **R-003 + R-002 + R-015/016** — ตรวจฟังและแก้การออกเสียงด้วย G2P จริง, ประเมิน Engine ที่ใช้เสียงเจ้าของได้, แล้วเพิ่ม Queue/Event Timing; R-004/R-025 มีฐาน Voice Studio และ 2 Engines แล้ว