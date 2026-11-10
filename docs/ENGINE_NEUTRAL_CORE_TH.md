# VoxWeaveTTS — Engine-Neutral Core v1

> Implementation preview v0.3.0.dev9 — ออกแบบให้ Core ทำงานได้โดยไม่ติดตั้งโมเดลหรือ ML Framework

## เป้าหมาย

สร้างระบบรับข้อความ ประมวลผลกฎคำอ่าน จัดคิวเสียง และให้บริการ API ที่ **ไม่ขึ้นกับ TTS Engine** โดยยังรองรับ FastThaiG2P, MakHam และสามารถเพิ่มโมเดลที่เราฝึกเองในอนาคตได้ด้วย Adapter สัญญาเดียวกัน

## โครงสร้าง

1. **Input Adapters** — Manual HTTP และ TXT/Markdown Reader ใช้ได้แล้ว; Simulator, Discord, YouTube ยังเป็นงานถัดไป
2. **Text Processor** — แปลงกฎ, Pronunciation, Source และแยก Spoken Text กับ Subtitle อิสระจาก Engine
3. **Speech Coordinator** — เก็บ Speech Job พร้อม ID, FIFO Queue, Dedup, Cancel, Status, จำกัด Memory และ Event
4. **Engine Registry** — ลงทะเบียน Factory ของโมเดล พร้อม Descriptor/Capability/Version (ไม่มีการโหลด Python Plugin อัตโนมัติ)
5. **WAV Renderer + Voice DSP** — รับ PCM16 จาก Adapter แล้วรวม Silence และ Export WAV พร้อมระยะเวลาต่อ Segment
6. **Playback Clock** — มี Browser Media CurrentTime + Segment Subtitle + OBS Overlay ใช้งาน Local แล้ว แต่ยังไม่มี Hardware Clock/Word-Level Alignment

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

## Subtitle Relay ส่วนกลางสำหรับทุก Engine

เมื่อ Browser เล่น WAV จริง จะรายงาน HTMLMediaElement.currentTime ไปยัง playback_state.py เพื่อเลือก Subtitle จาก Segment ที่ผ่านกฎกรองและให้ OBS Browser Source ดึงได้ที่ /overlay โดยไม่ต้องโหลดโมเดลในระบบเล่นเสียงและไม่ถือว่า Speech Job ready คือเริ่มเล่นแล้ว ดู [คู่มือ Playback/OBS](PLAYBACK_OVERLAY_TH.md)

## ขอบเขตข้อความภาษาไทย

เพิ่ม `text_boundaries.py` ซึ่งเป็นโมดูล Standard Library แบบ Engine-neutral: Estimated Subtitle จะเลือกจุดตัดเฉพาะช่องว่าง/เครื่องหมายคั่น ไม่ตัดกลาง Thai Run โดยประมาณจากจำนวนอักขระอีก; Document Reader ยังมีขนาด Chunk จำกัด แต่แสดงประเภทจุดตัดให้เห็นและลองตัดก่อนสระนำเมื่อไม่มีจุดคั่นธรรมชาติ. Manual Alignment ใช้กฎ Unicode เดียวกันป้องกันสระนำตกอยู่ลำพัง. อ่าน [Document Reader](DOCUMENT_READER_TH.md) และ [Overlay](PLAYBACK_OVERLAY_TH.md)

## Waveform Editor สำหรับการทำ Manual Cues

เพิ่มตัวอ่าน PCM16 WAV และ Canvas Waveform ใน Browser แยกเป็น web/waveform_editor.js รองรับซูม/เลื่อน/เลือกเวลาและ HiDPI จากเสียงที่สร้างโดย Engine ใดก็ได้ (หากให้ PCM16 WAV). การลากเลือกเวลาจะปรับเฉพาะฟอร์ม Manual Alignment ไม่กระทบ Engine หรือ WAV และไม่มีการบันทึกเสียงเพิ่ม ดู [Waveform Guide](WAVEFORM_EDITOR_TH.md)

## Manual Subtitle Cues จากการฟังจริง

SpeechCoordinator เก็บ Cue ที่ผู้ใช้ Mark เองไว้ในหน่วยความจำพร้อม Job (ไม่ลง Disk) โดยตรวจ Offset ว่าตรงกับ Display Text ที่ผ่าน Mask/Filter, ไม่ตัด Unicode และไม่ทับ Segment ที่ไม่ใช่ Speech; OBS Mode manual แสดงเฉพาะ Cue เหล่านี้ (ดู [Manual Alignment](MANUAL_ALIGNMENT_TH.md)). ยังคงไม่มี Automatic Forced Word Alignment

## ระบบวิเคราะห์ช่วงเสียง (Audio Activity)

เพิ่ม AudioAlignmentProvider แบบ Engine-neutral ซึ่งตรวจพลังงานจาก WAV จริงหลังการสังเคราะห์เสียงและส่ง Activity Intervals ไปยัง OBS Mode activity ได้ (ดู [Audio Alignment](AUDIO_ALIGNMENT_TH.md)). ยังเป็น Energy-Based Activity Detection ไม่ใช่ Forced Word Alignment และไม่ต้องใช้โมเดลเสริม

## OBS Subtitle แบบ SSE และ Estimated Mode

เพิ่ม Local SSE `/v1/playback/stream` ที่ส่งสถานะใหม่ทันทีเมื่อ Browser รายงานเวลาเล่นเสียง โดยมี HTTP Polling เป็น Fallback และตัวเลือก `/overlay?mode=estimated` ที่แสดงข้อความสั้นลงด้วยการประมาณเวลาในแต่ละ Segment. โหมดนี้ไม่ใช่ Word Alignment ที่ตรวจจับเสียงจริง และไม่เกี่ยวกับ TTS Engine ใดโดยเฉพาะ ดู [คู่มือ OBS](PLAYBACK_OVERLAY_TH.md)

## ข้อจำกัดและงานต่อไป

- Browser รองรับเล่น WAV ทีละช่วงจากเอกสาร พร้อม Pause/Resume/Stop และ Bookmark แบบ Local แล้ว แต่ มี Browser Media-Time Reporting และ OBS Overlay ระดับ Segment แล้ว แต่ **ยังไม่มี** Hardware-Level Clock, Word Alignment, Priority, Persistent Speech Queue หรือ Real-Time Audio Streaming
- ไม่ได้สร้างโมเดลใหม่หรือเทรนโมเดลในขั้นนี้
- การเล่น WAV ผ่าน Browser ส่งค่า CurrentTime เป็นระยะให้ Overlay แล้ว; ยังไม่ใช่ Audio Hardware Clock และไม่ใช่ Word Alignment
- เพิ่ม Input TXT/Markdown และแยกบท/ช่วงแล้ว ดู [Document Reader](DOCUMENT_READER_TH.md); เพิ่มการจดตำแหน่งอ่าน/เล่นทีละช่วงแล้ว ดู [Document Reader](DOCUMENT_READER_TH.md); งานถัดไปคือ Hardware/External Player Clock, Simulator และ Push Event Bus
- ก่อนพัฒนาโมเดล/Training Worker ให้ผ่านข้อกำหนดเรื่องสิทธิ์จาก [Commercial-First Policy](COMMERCIAL_LICENSE_POLICY_TH.md)

## ผลตรวจสอบ

- ทดสอบ Unit Tests ของ EngineRegistry กับ Engine จำลองที่ลงทะเบียนใหม่ โดยไม่แก้ Core และทดสอบ WAV กับกฎ Silence เดิม
- ทดสอบ SpeechCoordinator แบบไม่มีโมเดล: FIFO, Cancel ระหว่างรอ/กำลังสร้าง, Dedup, Queue/Audio Caps, TTL, Private Error, Event Order และ HTTP API
- ทดลอง POST /v1/jobs ด้วย MakHam CPU จริง: queued → rendering → ready, WAV 24 kHz 136,844 Bytes, Duration 2,850 ms (รวมข้อความไทยและเลข 55555)
- เก็บ Model Weights/Voice Samples ไว้นอก Repository และไม่เพิ่ม Engine ที่ยังไม่ผ่าน Commercial License Audit