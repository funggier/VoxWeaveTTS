# VoxWeaveTTS — แผนงานพัฒนาแบบละเอียด (Development Plan)

> จัดทำ: 10 พฤศจิกายน 2026 · เป้าหมาย: โปรแกรม Windows Portable ที่อ่านไทยได้ดี ปรับเสียงได้ รับข้อความสด และส่ง Subtitle ที่ตรงกับเสียงจริง  
> เอกสารนี้เป็น **แผน/เกณฑ์ยอมรับ** ไม่ใช่รายการความสามารถที่ส่งมอบแล้ว  
> สถานะล่าสุดที่ตรวจสอบก่อนแก้เอกสาร: Foundation v0.1.0, main `9a7f4e1` (ก่อน commit เอกสารชุดนี้); การเปลี่ยนแปลงหลังจากนี้ดู Git log เป็นหลัก

## 0. แหล่งที่มาของข้อกำหนดและหลักการวางแผน

แผนนี้รวบรวมความต้องการจากการสนทนาเรื่อง TTS ภาษาไทยและเสียงส่วนตัว:
- ปัญหานิยายอ่านคำไทยผิด เช่น “อมตะ”, “เซียน”
- ใช้เสียงที่กำหนดเอง ปรับเนื้อเสียง ความเร็ว สูงต่ำ ความเป็นธรรมชาติ และ Preset
- ตัด/แทนคำ ปิดเสียงเป็นช่วงเวลาที่แน่นอน เปลี่ยน Subtitle ได้ต่างจากข้อความพูด
- อ่านนิยายและอ่านข้อความสดจาก Discord, YouTube Live Chat/Comments
- มี API สำหรับแอปภายนอก และ Event ที่ประกอบด้วยข้อมูลการพูด + Subtitle
- พกพาในโฟลเดอร์เดียว แตก ZIP ใช้งาน โดยไม่ติดตั้ง Python

เพื่อไม่ให้สร้าง UI สวยก่อนแต่ระบบหลักยังใช้งานไม่ได้ จะพัฒนาแบบ **Vertical Slice**: ข้อความ → กฎ → เสียงจริง → Playback → Event/Subtitle → Portable; แต่ละระยะมี Demo และ Tests สั้น ๆ ที่ทำซ้ำได้

**สิ่งที่มีแล้ว:** ตัวกรอง/คำอ่าน/แผนข้อความ/HTTP Preview/เว็บทดลอง/Unit Tests และเพิ่มเติม **FastThaiG2P CPU ONNX สร้าง WAV ภาษาไทยจริงได้แล้วใน M1 Preview**
**สิ่งที่ยังไม่มี:** Voice Cloning/Voice Studio ที่ปรับเสียงละเอียด/Live Events/Connectors/Portable Binary; ไม่ควรติ๊กผ่านจนกว่าจะทดสอบจริง

## 1. ข้อกำหนดข้ามทุกระยะ (Definition of Done)

ทุก Milestone จะถือว่าเสร็จเมื่อ:
1. รันบน Windows จริงได้ตามวิธีใน README; มีผลทดสอบ unit/integration ที่อธิบายวิธีทำซ้ำ
2. Error และ Timeout มีความหมาย ไม่ทำให้กระบวนการค้างหรือส่ง Subtitle ค้าง
3. ไม่เก็บเสียง/Token/ข้อความที่กรองใน Repo หรือ Log โดยไม่จำเป็น
4. มี API Schema หรือ Interface ชัดเจน แยกโมดูลเปลี่ยนได้ และระบุค่าที่ Engine ไม่รองรับ
5. อัปเดต README_TH, README, docs/API.md, docs/ROADMAP.md รวมถึงตัวอย่างใช้งานจริง
6. การใช้จริงไม่ต้องคาดเดาจาก “ปุ่มมีอยู่” แต่ต้องยืนยันจาก Audio/API/Event/CI หรือการเปิดบนเครื่องสะอาด
7. อธิบายข้อจำกัดที่ยังพบและผลข้างเคียงที่ยอมรับได้

## 2. ลำดับงานและ Dependencies

```text
M0 Foundation ──> M1 Thai TTS Audio ──> M2 Voice Studio / Long Text
                           │                       │
                           └──────> M3 Playback Coordinator + Event Bus
                                                    │
                                      ┌─────────────┴────────────┐
                                      ▼                          ▼
                            M4 Live Connector/API        M5 Subtitle Overlay
                                      └─────────────┬────────────┘
                                                    ▼
                                         M6 Portable & Release
```

หมายเหตุ: **หลัก Portable** (relative paths, local cache, data isolation) ต้องใช้ตั้งแต่ทุกระยะแม้แพ็ก EXE จะทำตอนท้าย ส่วน Subtitle แบบ Full Message สามารถทดสอบกับข้อความจำลองก่อน Live Connector เสร็จได้

## 3. M0 — Foundation: โครงสร้างและทดสอบข้อความ

**สถานะ:** เสร็จแล้วในระดับ Foundation; ไม่ใช่ TTS ใช้งานจริง

งานที่มีแล้ว:
- [x] โปรเจกต์ `VoxWeaveTTS`, GitHub Public, MIT สำหรับโค้ด
- [x] Python package และ Local HTTP Server (`127.0.0.1:8765`)
- [x] `POST /v1/text/process`, Status/Rules/Pronunciations GET
- [x] กฎ Literal Replace/Skip/Silence พร้อมแยก `spoken_text`, `display_text`, Segment Offset
- [x] Dictionary Hint และตัวอย่างกฎภาษาไทย
- [x] HTML Text Preview, Unit Tests และ GitHub Actions
- [ ] ตรวจจับ boundary ภาษาไทย/ตัวสะกดหลายบริบท และสร้าง Regression Corpus ให้ครอบคลุมมากกว่า Literal Matching

**เกณฑ์ยอมรับของ Foundation:** “อมตะ” แสดงบน Subtitle เหมือนเดิมแต่ Spoken Text ใช้คำอ่านที่กำหนด; คำกรองไม่ปรากฏใน Spoken/Display ของผลลัพธ์เมื่อ Mask; Silence เป็น Segment แยก ไม่แปลงเป็น *** ให้ TTS อ่าน

**ข้อจำกัด:** ข้อความนี้ยังไม่ได้สร้างเสียง เสียงเงียบยังไม่ถูกเรนเดอร์เป็น PCM จริง

## 4. M1 — Thai TTS Engine และไฟล์เสียงจริง

**สถานะปัจจุบัน: M1 Partial** — เพิ่ม VoiceEngine Protocol, FastThaiG2P CPU ONNX Adapter, WAV 24 kHz Mono, Silence PCM, API `/v1/speech` และปุ่มเล่นเสียงใน Web UI แล้ว ทดสอบจริงสร้างไฟล์ WAV สำเร็จแต่ยัง **ไม่ยืนยันการออกเสียงภาษาไทยด้วยการตรวจฟัง** ดู [M1_AUDIO_TH.md](M1_AUDIO_TH.md)

**เป้าหมาย:** กดปุ่มแล้วได้ไฟล์ WAV จากข้อความไทย พร้อมประเมินว่าเสียงจริงออกถูกต้องหรือไม่

งาน:
- [x] ออกแบบเบื้องต้น `VoiceEngine` Protocol, Capability Discovery และ `render_wav` (ยังไม่มี `cancel()`/การ Streaming)
- [ ] ประเมิน Engine ภาษาไทยที่ติดตั้งได้จริง (รวมขนาด/CPU-GPU/Latency/License/Offline/Custom Pronunciation) **ไม่ผูกขาดกับตัวใดตัวหนึ่ง**
- [x] เลือก FastThaiG2P CPU ONNX เป็น Engine ขั้นต้น และทำ Adapter แบบรายงาน Unsupported อย่างตรงไปตรงมา (ยังต้องเสริม Timeout/Cancellation)
- [x] สร้าง WAV PCM16 Mono 24 kHz พร้อม Metadata ระยะเวลาต่อ Segment ภายใน Engine
- [x] แปลง Speech/Silence/Skip Segment เป็น Audio WAV; Silence 400 ms เป็น Zero PCM จริง
- [ ] ทดลองคำอ่านไทยยาก/วรรณยุกต์/ชื่อเฉพาะโดยฟังจริง และบันทึกผลผ่านชุดคำทดสอบ
- [x] ตรวจ Capability รายงานเสียง `thai_som` แบบคงที่และ Speed เท่านั้น; Voice Cloning/Pitch/Formant/Emotion ยังไม่รองรับ
- [ ] กำหนด Audio Cache Key ตามข้อความที่ผ่านการแปลง + Engine Version + Profile + ค่าปรับ + กฎ + Model Hash เพื่อป้องกันใช้ Cache ผิด
- [ ] ทดสอบข้อความยาวไม่ให้กิน RAM สูง; แบ่งคำพูดเป็นช่วงและจัดการ Backpressure
- [ ] สรุป License/Attribution ของ Engine และ Model โดยไม่รวมโมเดลเข้า Public Repo

**Acceptance test:**
1. จากข้อความ “อมตะ” สร้างไฟล์ WAV ที่เล่นได้และตรวจฟังว่าอ่านใกล้เคียง “อะ-มะ-ตะ”; หากผิด ต้องบันทึกเป็น Issue ไม่ติ๊กผ่าน
2. Mask “คำต้องห้าม” แล้วเสียงไม่มีคำนั้น; มี Silence ตามระยะที่กำหนด (ยอมรับ tolerance ตาม Audio Sample Rate)
3. Engine ที่ไม่รองรับ Voice Cloning ตอบ `unsupported` ตรงไปตรงมา ไม่แสร้งว่าทำได้
4. หยุดประมวลผลขณะทำงานได้และไม่มี Process/Cache ที่ค้างอย่างไม่จำเป็น

**ความเสี่ยง:** โมเดลไทยและ Voice Clone คุณภาพ/ความเร็วต่างกัน; บางโมเดลมีข้อจำกัด Non-Commercial ดังนั้น Full Package ต้องตรวจสิทธิ์แยก

### ความคืบหน้าเพิ่มเติม M1.1 — ล็อกความสุ่มของเสียง

- [x] ตรวจพบว่าการใช้ ONNX Session เดิมซ้ำ แม้ข้อความเท่ากัน ก็สามารถได้เสียงต่างกัน โดยเฉพาะคำซ้ำ เช่น `ฮ่า ฮ่า ฮ่า`
- [x] ใช้ Seed ตั้งค่าก่อนสร้าง Session ใหม่ต่อหนึ่งงานเสียง เพื่อได้ WAV ที่ทำซ้ำได้บน Runtime ปัจจุบัน
- [x] เปิดปรับ Seed ผ่าน Web UI/API และบันทึกค่าที่เลือกภายในโฟลเดอร์โปรเจกต์
- [ ] ตรวจฟังหาค่า Seed และ Engine ที่ให้เสียง `ฮ่า` เหมือนเสียงที่ต้องการจริง (ยังไม่รับรองความถูกต้อง)
- [ ] ประเมินลดค่าเริ่มต้นโหลด Model Session ต่อคำขอ เพื่อรองรับข้อความสดในระยะถัดไป

## 5. M2 — Voice Studio, เสียงส่วนตัว และอ่านเรื่องยาว

**เป้าหมาย:** ปรับเสียงให้ถูกใจด้วยการลองฟังจริง รวมทั้งใช้กับนิยายได้เป็นตอน

งาน:
- [ ] หน้า Voice Studio: เลือก Engine, Voice Profile, Preview Text, Play/Stop และ A/B Comparison
- [ ] โปรไฟล์เสียงอ้างอิง (ใช้เฉพาะเสียงที่มีสิทธิ์) เก็บใต้ `voices/` ไม่อัปโหลด
- [ ] Preset ต่อ Engine/Voice พร้อม Versioning/Export/Import และ Reset
- [ ] Speed, Pitch, Formant, Brightness/EQ, Expressiveness, Pause; แยก **ก่อนสร้างเสียง** กับ **DSP หลังสร้างเสียง** และแสดง Supported/Unsupported
- [ ] กำหนดขอบเขต Pitch เพื่อไม่ทำลายรูปวรรณยุกต์ไทย และมีคำทดสอบมาตรฐาน
- [ ] คลังพจนานุกรมคำอ่านและกฎแทนคำ: เพิ่ม แก้ ลบ Import/Export และ Scope Global / Per-Book / Per-Source
- [ ] รองรับ TXT/MD และการแบ่งบท; สำหรับ Markdown ให้ไม่อ่าน Syntax/Code Block โดยไม่จำเป็น
- [ ] Speech Cache ทีละช่วง ทำใหม่เฉพาะตอนที่แก้คำอ่านหรือข้อความ
- [ ] Resume Position, Playback Controls, เสียงอ่านตอนยาวและแสดงข้อผิดพลาดเฉพาะช่วง
- [ ] ไม่เปิดเผยข้อมูลอ้างอิงเสียงใน Logs, API response หรือ Repository

**Acceptance test:** สร้างเสียงประโยคเดียวกัน 2 Presets และฟังเปรียบเทียบได้; เก็บ/รีโหลด Preset ได้; แก้คำอ่านหนึ่งช่วงของบทแล้วสร้างใหม่เฉพาะช่วงนั้น; ปรับค่าที่โมเดลไม่รองรับต้องมีข้อความแจ้ง ไม่เงียบหายหรือหลอกผู้ใช้

## 6. M3 — Speech Coordinator, Queue และ Event Contract

**เป้าหมาย:** ย้ายจากการสร้างไฟล์เสียงเป็นการ “สร้าง/เล่นหนึ่ง Speech Session” ที่มี ID และสถานะ

งาน:
- [ ] แบบข้อมูล `SpeechJob`/`SpeechSession`: `speech_id`, `source`, `source_message_id`, `stream_id`, `voice_id`, `original` (private), `display` (public), `segments`, timestamps
- [ ] สถานะ: `queued`, `preparing`, `ready`, `playing`, `paused`, `completed`, `cancelled`, `failed`
- [ ] นโยบายคิว: Sequential, Latest, Priority, Manual, Filtered พร้อมความจุสูงสุดและ Deadline/TTL
- [ ] Playback Clock อ้างอิงการเล่น PCM จริง; ไม่สร้าง Timestamp จากตอนที่ข้อความเข้ามาหรือไฟล์ถูกสร้างเสร็จ
- [ ] Segment ประเภท Speech, Silence, Skip, Replacement มีช่วงเวลา อ้างอิง Source Span และยกเลิก/ข้ามคิวได้
- [ ] Event Bus แยก Playback กับ Consumer: `speech.queued/ready/started/segment/paused/resumed/completed/cancelled/failed`
- [ ] Event Version, Sequence, Reconnect Snapshot, Idempotency/Dedup
- [ ] HTTP API ส่ง Speech Job และควบคุม Playback; WebSocket/stream เฉพาะที่จำเป็น
- [ ] ถ้ามีการกรองหรือซ่อนคำ ต้องไม่ส่ง Original Text ที่ไม่ควรเผยแพร่ไป Public Event Payload
- [ ] เลือก Output Device / Virtual Audio Route; ระวังไม่เล่นซ้ำเมื่อ OBS ดึงเสียงเอง

**Acceptance test:** ในการเล่น 3 ข้อความพร้อมกันมี Event ตามลำดับที่กำหนด, Pause/Resume ทำให้ Subtitle ไม่วิ่ง, Cancel ส่ง Event ล้างข้อความ, reconnect กลับมาแล้วเห็นสถานะปัจจุบันโดยไม่ย้อนอ่านข้อความเดิมซ้ำ

## 7. M4 — API ภายนอกและ Discord / YouTube

**เป้าหมาย:** รับข้อความสดเข้าระบบคิวได้โดยไม่ผูกโมเดลกับ Service

งาน:
- [ ] HTTP API / WebSocket ที่ประกาศเวอร์ชันและ Schema; เปิดเฉพาะ localhost โดยค่าเริ่มต้น
- [ ] แยก `InputAdapter` แบบ Test Simulator, Manual API, Discord Bot, YouTube Live, YouTube Comments
- [ ] Auth สำหรับ Bot/OAuth และ API Key เมื่อเปิดให้เครื่องอื่นเข้าถึง, Least Privilege และ Rate Limit
- [ ] Discord: เลือก Server/Channel, Allowed Users/Roles, Message Intent/Permission, คำสั่งอ่าน
- [ ] YouTube Live: ใช้ Live Chat API/stream ตามสิทธิ์และข้อจำกัด; สำหรับ Comments ใช้ Polling/Dedup โดยแยกจาก Live
- [ ] ป้องกัน Spam: ความยาว, ข้อความซ้ำ, URL, Emoji, ข้อความที่เป็นคำสั่ง, Priority, Reconnect, Backoff, API Quota
- [ ] กฎกรอง/คำอ่านแยกตาม Source, Channel, Voice Profile; ตั้งแบบ Global ได้
- [ ] Message Simulator สำหรับทดสอบโดยไม่ต้องใช้ Credential บริการจริง
- [ ] UI สถานะ Connection/Queue/Last Error โดยไม่เผยแพร่ Token ใน Log

**Acceptance test:** ส่งข้อความผ่าน API และ Simulator แล้วอ่าน/รับ Event ได้เหมือนข้อความจริง; เชื่อม Discord/YouTube ตามสิทธิ์จริง; ดึงแชทซ้ำต้องไม่อ่านซ้ำ; เมื่ออินเทอร์เน็ตหลุดต้องกลับมาทำงานโดยไม่ค้างตลอด

## 8. M5 — Subtitle Sync / OBS Overlay / Consumer API

**เป้าหมาย:** แสดง Subtitle ที่ตรงกับเสียง TTS ซึ่งกำลังเล่นจริงบน OBS และโปรแกรมอื่น

งาน:
- [ ] Browser Overlay พื้นหลังโปร่งใสสำหรับ OBS (`/overlay/subtitles`) มี Safe Area/Font/Color/Outline/ตำแหน่ง/ขนาด
- [ ] Display Text แยกจาก Spoken Text พร้อมชื่อผู้ส่ง/Source ตามสิทธิ์ที่ผู้ใช้เปิดไว้
- [ ] 3 ระดับ: Full Message → Sentence/Segment → Word Highlight (เฉพาะมี Timing จริง/Forced Alignment)
- [ ] WebSocket Client รับ Event + Snapshot ตอนเชื่อมต่อใหม่
- [ ] แสดงเมื่อ `speech.started`, เปลี่ยนตาม Segment, ซ่อนเมื่อ `completed/cancelled/failed`; ห้ามยึดเวลาแชทที่เข้ามา
- [ ] ระบุ Offset สำหรับชดเชยความล่าช้า Audio Output/OBS โดยไม่แก้ข้อมูลต้นฉบับ
- [ ] ประมวลผล HTML แบบ safe text เท่านั้น (ไม่ใช้ innerHTML กับแชท)
- [ ] ทดสอบ Alt Tab, OBS Scene Switch, pause/seek/cancel, concurrent event และ Browser Source reconnect
- [ ] ตัวอย่าง Consumer ภายนอก (Web/Unity) โดยไม่บังคับ OBS

**Acceptance test:** Simulator ส่งแชท 3 ข้อความ; Event, เสียงและ Overlay เรียงตรงกัน; ช่วงเงียบแสดง Mask แต่ไม่มีเสียง; เมื่อข้ามข้อความ Subtitle ไม่ติดอยู่บนหน้าจอ; เปลี่ยน Scene/รีเชื่อมต่อไม่เล่นซ้ำ

## 9. M6 — Windows Portable Packaging และการแจกจ่าย

**เป้าหมาย:** ZIP ที่แตกแล้วเปิดได้จริงบน Windows โดยไม่ต้องติดตั้ง Python หรือ Developer SDK

งาน:
- [ ] Build Executable สำหรับ `VoxWeaveTTS.exe` และการรันเฉพาะ API Server
- [ ] Bundled Runtime/Native Dependencies โดยไม่อ้างพาธ C:/ หรือ Python ภายนอก
- [ ] Path Resolver ยึดตำแหน่งโปรแกรม; `data/`, `voices/`, `models/`, `cache/`, `output/` ภายใน Root หรือย้ายได้ตามการตั้งค่า
- [ ] ตั้ง TEMP/HF_HOME/TORCH_HOME (ตาม Engine ที่เลือก) ไปอยู่ในโฟลเดอร์ที่เหมาะสมโดยไม่ทำให้ Dependency พัง
- [ ] GPU/CPU Detection และ Fallback; มีหน้าแสดงอุปกรณ์/ข้อจำกัด/ขนาดโมเดล
- [ ] ทดสอบเปิด/ปิด/ย้ายไปไดรฟ์อื่นและโฟลเดอร์ชื่อไทย/ช่องว่าง; ทดสอบบน Windows สะอาด
- [ ] แพ็ก 2 รูปแบบตามความเหมาะสม: `VoxWeaveTTS-vX.Y.Z-portable.zip` (ไม่รวมโมเดลที่ต้องดาวน์โหลด) และ optional `-full-portable.zip` (เฉพาะโมเดลที่อนุญาตให้แจก)
- [ ] สำรอง Settings ก่อน Migration, Verify Data Schema; ไม่ลบผู้ใช้ตั้งไว้
- [ ] ตรวจ Licenses, ป้องกัน Secret Leak, Hash SHA-256, Release Notes, Tag/CI และ Smoke Test ของ ZIP ที่แจกจริง

**Acceptance test:** นำ ZIP ไปเครื่อง Windows เป้าหมายที่ไม่มี Python เปิดและสร้างเสียงภาษาไทยได้จริง, ปรับคำอ่าน/เสียง/Filter ได้, ใช้งาน API & OBS Overlay ได้ และย้ายทั้งโฟลเดอร์โดยคงการตั้งค่าเดิม

## 10. ชุดทดสอบสำคัญ (Regression Matrix)

| หมวด | Input / สถานการณ์ | Expected |
|---|---|---|
| คำอ่านไทย | `อมตะ` → hint `อะ มะ ตะ` | Subtitle ยังคงคำว่า `อมตะ`, เสียงจริงตรวจฟังถูกต้อง |
| วรรณยุกต์ | `เซียน` | ไม่กลายเป็น `เซี่ยน` เมื่อใช้ Engine/Preset ที่รับรอง |
| Replacement | `55555` → `ฮ่า ฮ่า ฮ่า` | เสียงหัวเราะตามคำใหม่, Subtitle ตามกฎที่เลือก |
| Mask + Silence | `คำต้องห้าม` → `***`, 400 ms | สร้าง Silence จริง, Event/Subtitle ตรงเวลา, ไม่มีคำต้นฉบับรั่ว |
| Mask + Skip | กรองคำแล้วข้าม | ไม่มีเสียงและไม่มีระยะหยุดเพิ่ม |
| Multi-source | Discord/YouTube ข้อความซ้ำ | Dedup ตาม Source ID/Message ID |
| Queue | Burst 30 messages | ไม่มีคิวขยายไม่สิ้นสุด; Policy แสดงผลตามที่ตั้ง |
| Cancellation | ข้ามขณะเล่น | Audio/Overlay หยุด/หาย และแจ้ง Cancel |
| Subtitle | เปลี่ยน Scene/Browser reconnect | ดึง Snapshot คืนสถานะได้ |
| Security | ข้อความคล้าย HTML/JS, ยาวเกิน | แสดงเป็น Text, กรอง/จำกัดอินพุต ปฏิเสธอย่างปลอดภัย |
| Portable | ย้ายไดรฟ์/ไม่มี Python | รัน Runtime ที่ Bundle และยังโหลด Settings/Models ได้ |

## 11. ตัวชี้วัดก่อนกำหนดเป้าตัวเลข (Non-fabricated quality metrics)

จะยัง **ไม่อ้างค่าประสิทธิภาพหรือความเร็ว** จนกว่าจะวัดบนเครื่องและโมเดลจริง เริ่มจากบันทึก:
- Time-to-first-audio (TTFA) และระยะเวลาสร้างเสียงต่อ 100 ตัวอักษร
- Real-time factor (RTF) / Streaming buffer underruns / RAM-VRAM usage
- อัตราคำอ่านผิดในชุดคำไทยที่ผู้ใช้ฟังตรวจและประเมินอย่างเป็นระบบ
- Subtitle offset เทียบกับเวลาเริ่มเล่นเสียงจริงและ jitter ใน OBS
- อัตราข้อความซ้ำ, คิวค้าง, Drop และ Cancel ไม่สำเร็จ
- Portable smoke test: first-run, move folder, without Python, offline after model installed

**การตั้งค่าขีดจำกัด** (เช่น TTFA < 1 วินาที) เป็นเป้าทดลองภายหลัง ไม่ใช่ความสามารถที่มีแล้ว; ต้องกำหนดตาม Hardware/Engine จริง

## 12. ความเสี่ยง การตอบสนอง และงานที่ต้องตัดสินใจ

| ความเสี่ยง | แนวทาง |
|---|---|
| Model อ่านไทยผิด/วรรณยุกต์เพี้ยน | Regression Corpus + ฟังจริง + G2P/Phoneme Adapter, เปลี่ยน Engine ได้ |
| Voice Clone ไม่เหมือนเสียงตัวอย่าง | ทดสอบ Zero-shot ก่อน, Fine-tune ภายหลังเฉพาะถ้าจำเป็น |
| DSP Pitch/Formant ทำเสียงผิดธรรมชาติ | แยก Native/External DSP, A/B และขอบเขตปรับที่เหมาะสม |
| Model สร้างเสียงช้ากว่าแชทเข้า | Queue Policy, ขนาดคิว, TTL, Chunking, Worker Health |
| Word-level Caption ไม่ตรงจริง | ต้องใช้ Forced Alignment/Timing จริง; เริ่มจาก Full Message |
| Platform API เปลี่ยน/Quota เกิน | Adapter Isolation, Backoff และ Simulator, อ้างอิงเอกสารล่าสุด |
| Offline/Portable ใช้ไม่ได้บนบางเครื่อง | ตรวจ Driver/Runtime และ CPU fallback, แพ็กทดสอบสะอาด |
| เผยแพร่ไฟล์เสียง/Token/โมเดลผิดสิทธิ์ | .gitignore, secret audit, license manifest, manual release gate |
| ใช้งานหลาย Consumer ทำให้เสียงซ้ำ | Audio Output Owner เดียว, Event Consumers ไม่เล่น Audio ซ้ำโดยค่าเริ่มต้น |

## 13. ลำดับเริ่มทำงานครั้งถัดไป (Next session checklist)

1. ยืนยัน Git state, HEAD, uncommitted changes และผล CI ก่อนแก้
2. เริ่มที่ **M1**: สร้าง Engine Interface และ Capability Contract พร้อม Mock Engine
3. ทำชุดข้อความไทยทดสอบคำอ่าน/เสียงให้เป็น fixture, ไม่ใช้ไฟล์เสียงส่วนตัวใน Repo
4. ประเมิน Backend TTS ที่รองรับภาษาไทยจริง (Hardware + License + Audio Quality)
5. เชื่อม Engine 1 ตัวเพื่อให้ `POST /v1/speech` สร้าง WAV ได้ พร้อม Silence จริง
6. ทดสอบ Audio และอัปเดตเอกสารตามผลจริง; **อย่าข้ามไปพัฒนา OBS/Discord ก่อนรู้ว่าเสียงออกได้**

## 14. เอกสารที่เกี่ยวข้อง

- [ที่มาและเหตุผล](PROJECT_VISION_TH.md)
- [ข้อกำหนดและความสามารถตามสถานะ](REQUIREMENTS_TH.md)
- [Roadmap checklist](ROADMAP.md)
- [Architecture](ARCHITECTURE.md), [API](API.md), [Portable](PORTABLE.md), [Security](SECURITY.md)