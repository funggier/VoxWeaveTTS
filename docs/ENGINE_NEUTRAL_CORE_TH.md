# VoxWeaveTTS — Engine-Neutral Core v1

> Implementation preview v0.3.0.dev1 — ออกแบบให้ Core ทำงานได้โดยไม่ติดตั้งโมเดลหรือ ML Framework

## เป้าหมาย

สร้างระบบรับข้อความ ประมวลผลกฎคำอ่าน จัดคิวเสียง และให้บริการ API ที่ **ไม่ขึ้นกับ TTS Engine** โดยยังรองรับ FastThaiG2P, MakHam และสามารถเพิ่มโมเดลที่เราฝึกเองในอนาคตได้ด้วย Adapter สัญญาเดียวกัน

## โครงสร้าง

1. **Input Adapters** — Manual HTTP และ TXT/Markdown Reader ใช้ได้แล้ว; Simulator, Discord, YouTube ยังเป็นงานถัดไป
2. **Text Processor** — แปลงกฎ, Pronunciation, Source และแยก Spoken Text กับ Subtitle อิสระจาก Engine
3. **Speech Coordinator** — เก็บ Speech Job พร้อม ID, FIFO Queue, Dedup, Cancel, Status, จำกัด Memory และ Event
4. **Engine Registry** — ลงทะเบียน Factory ของโมเดล พร้อม Descriptor/Capability/Version (ไม่มีการโหลด Python Plugin อัตโนมัติ)
5. **WAV Renderer + Voice DSP** — รับ PCM16 จาก Adapter แล้วรวม Silence และ Export WAV พร้อมระยะเวลาต่อ Segment
6. **Playback Clock** — ยังไม่พัฒนา; เมื่อมีจริงจะเชื่อม OBS / Event Stream และ Subtitle กับเวลาที่เสียงเล่นจริง

## Engine Adapter Contract v1

ไฟล์: src/voxweavetts/engine_contract.py

| ชื่อ | ข้อกำหนด |
|---|---|
| EngineInfo.id | รหัส Engine รูปแบบ a-z, 0-9, - หรือ _ ไม่ซ้ำกัน |
| EngineInfo.voice_id | ชื่อเสียง (หนึ่งเสียงต่อ Adapter ใน Contract v1) |
| EngineInfo.sample_rate | 8,000–96,000 Hz |
| EngineInfo.capabilities | ความสามารถจริง เช่น Speech, Speed, Voice Cloning |
| EngineInfo.assets_ready / runtime_ready | ต้องรายงานตามความพร้อมจริง |
| EngineInfo.adapter_api_version | เท่ากับ 1 |
| EngineInfo.commercial_status | ค่าเริ่มต้น review_required; ไม่รับรองว่าใช้การค้าได้อัตโนมัติ |
| VoiceEngine.generate(text, speed) | คืน Byte Stream ของ **PCM16 Mono Little-endian โดยไม่มี WAV Header** |
| EngineRegistry.register(id, describe, create) | ลงทะเบียนเฉพาะ Python Code ที่ตรวจ/เชื่อถือแล้ว |

API Registry อยู่ใน src/voxweavetts/speech.py ที่ฟังก์ชัน engine_registry() และมี Built-in Adapters ลงทะเบียนไว้สองตัว

**การเพิ่มโมเดลที่ฝึกเอง:** สร้าง Adapter Class ในโมดูลของโมเดลเอง โดยมี id, sample_rate, generate(text,speed), ฟังก์ชัน describe คืน EngineInfo และ Factory create(seed) แล้วเรียก engine_registry().register(...) จาก Launcher/Entry Point ที่เชื่อถือได้ก่อนเปิด HTTP Server ไม่จำเป็นต้องแก้ Text Processor, Queue, HTTP API หรือ WAV Renderer

ไม่มีการสแกนโฟลเดอร์แล้วนำ Python มารันอัตโนมัติ จึงลดความเสี่ยงจาก Plugin ที่ไม่รู้แหล่งที่มา การลงทะเบียนไม่ได้ถือว่า License ผ่านตรวจสอบเชิงพาณิชย์แล้ว

## Speech Coordinator — ทำงานโดยไม่มี Engine จริงได้

ไฟล์: src/voxweavetts/speech_coordinator.py

รับ **แผนข้อความที่ผ่านกฎแล้ว** และ Renderer Callable ใน Constructor จึงสามารถใช้ Mock Engine สำหรับทดสอบ FIFO, Error, Queue, Events โดยไม่ต้องมี ONNX / PyTorch / Voice Model

สถานะปัจจุบัน:

- queued → rendering → ready
- cancelled หรือ failed เมื่อมีการยกเลิก/ผิดพลาด

Events Version 1: speech.queued, speech.rendering, speech.ready, speech.cancelled, speech.failed

API ที่เพิ่ม:

| Method / Path | หน้าที่ |
|---|---|
| POST /v1/jobs | เข้าคิวด้วยข้อความ/Rules/Engine/Voice/Controls ชุดเดียวกับ /v1/speech; ต้อง Header X-VoxWeaveTTS-Intent: queue-speech |
| GET /v1/jobs | รายการ Job ปัจจุบัน |
| GET /v1/jobs/{speech_id} | Snapshot ของ Job |
| GET /v1/jobs/{speech_id}/events | Events แบบลำดับ/เวอร์ชัน |
| GET /v1/jobs/{speech_id}/audio | รับ WAV เมื่อ ready; หากยังไม่พร้อมคืน 409 |
| POST /v1/jobs/{speech_id}/cancel | ยกเลิก; ต้อง Header X-VoxWeaveTTS-Intent: cancel-speech-job |

หาก Input Adapter ส่ง source และ source_message_id ที่ซ้ำกัน ระบบจะ Dedup โดยไม่สร้างงานใหม่

มีการจำกัด 12 Jobs ในหน่วยความจำ, WAV สูงสุด 16 MB ต่อ Job, WAV ทั้งหมดไม่เกิน 64 MB และล้างงานที่เสร็จเมื่ออายุเกิน 15 นาที หรือเมื่อจำเป็นต้องมีที่ว่างสำหรับงานใหม่ หากคิวยังเต็มจะตอบ 429

**สำคัญ:** ready แปลว่า **ไฟล์เสียงสร้างเสร็จ** ไม่ได้หมายความว่าเสียงเริ่มเล่น/จบแล้ว และ start_ms/end_ms อ้างอิง **จำนวน Audio Samples ที่ผลิต** ไม่ใช่ Playback Clock จริง จึงยังไม่ใช้เป็นคำรับรอง Subtitle Synchronization กับ OBS

Cancel ระหว่าง ONNX กำลัง Inference ไม่ได้หยุด Model Call กลางคัน แต่จะตั้งสถานะ Cancel และทิ้งไฟล์เมื่อ Inference เสร็จ

Queue ยังเก็บอยู่ใน RAM เท่านั้น และไม่อยู่ข้าม Restart; ข้อความต้นฉบับ/Spoken Plan ถูกเก็บเป็นข้อมูลส่วนตัวระหว่างรอประมวลผลและจะถูกล้างหลังได้ผลสำเร็จหรือผิดพลาด Public Job/Event API คืนเฉพาะข้อความ Subtitle ที่ผ่านการกรองแล้ว ไม่มี Spoken/Original และ Exception ของโมเดล

## ข้อจำกัดและงานต่อไป

- ยังไม่มี Audio Device Playback, Pause/Resume, Priority, Persistent Queue, Real-Time Audio Streaming หรือ OBS Subtitle Sync
- ไม่ได้สร้างโมเดลใหม่หรือเทรนโมเดลในขั้นนี้
- การเล่น WAV ผ่าน Browser เป็นการเล่นจาก UI แต่ยังไม่เชื่อม Event กับ Audio Playback Clock
- เพิ่ม Input TXT/Markdown และแยกบท/ช่วงแล้ว ดู [Document Reader](DOCUMENT_READER_TH.md); งานถัดไปคือบันทึกตำแหน่งอ่าน, Playback Controller, Simulator และ Timeline Event Bus
- ก่อนพัฒนาโมเดล/Training Worker ให้ผ่านข้อกำหนดเรื่องสิทธิ์จาก [Commercial-First Policy](COMMERCIAL_LICENSE_POLICY_TH.md)

## ผลตรวจสอบ

- ทดสอบ Unit Tests ของ EngineRegistry กับ Engine จำลองที่ลงทะเบียนใหม่ โดยไม่แก้ Core และทดสอบ WAV กับกฎ Silence เดิม
- ทดสอบ SpeechCoordinator แบบไม่มีโมเดล: FIFO, Cancel ระหว่างรอ/กำลังสร้าง, Dedup, Queue/Audio Caps, TTL, Private Error, Event Order และ HTTP API
- ทดลอง POST /v1/jobs ด้วย MakHam CPU จริง: queued → rendering → ready, WAV 24 kHz 136,844 Bytes, Duration 2,850 ms (รวมข้อความไทยและเลข 55555)
- เก็บ Model Weights/Voice Samples ไว้นอก Repository และไม่เพิ่ม Engine ที่ยังไม่ผ่าน Commercial License Audit