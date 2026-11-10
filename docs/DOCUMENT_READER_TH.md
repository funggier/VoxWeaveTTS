# VoxWeaveTTS — Engine-Neutral Document Reader (TXT / Markdown)

> Implementation preview v0.3.0.dev5 — ข้อความ/เอกสารใช้ Core ได้โดยไม่ต้องติดตั้ง TTS Engine; การสร้าง WAV ยังต้องมี Engine

## เป้าหมาย

สร้างระบบเปิดไฟล์ TXT/Markdown แบ่งบทและแบ่งช่วงอ่านข้อความเพื่ออ่านนิยายได้ โดยไม่ผูกกับ FastThaiG2P, MakHam หรือโมเดลของเราในอนาคต

## ความสามารถที่ใช้ได้ตอนนี้

- เปิด .txt และ .md จาก Browser บนเครื่องผู้ใช้ รองรับการเลือก Text Encoding เป็น **UTF-8** หรือ **Thai Windows-874** (แนะนำ UTF-8)
- Markdown: ลบเครื่องหมาย Heading/Emphasis, Code Fences, Inline Code, Image, URL ของลิงก์, HTML Script/Style/Pre และ YAML Frontmatter ออกก่อนนำไปอ่าน
- TXT: ตรวจหัวเรื่องรูปแบบไทย เช่น บทที่ ๑, ตอนที่ 2 และ Chapter 1; Markdown ใช้ Heading Level 1–6
- แบ่งเป็น **Chapter** และ **Chunk** ที่ความยาวสูงสุด 100–450 ตัวอักษร (ค่าเริ่มต้น 350), พยายามตัดที่จุดจบประโยคและช่องว่างก่อน หลีกเลี่ยงแยกวรรณยุกต์ไทยเดี่ยว
- มีการแบ่งหน้ารายการ Chunk เพื่อให้เอกสารยาวไม่ต้องส่งข้อความของทุก Chunk กลับมาในแต่ละครั้ง
- UI เลือกบท/ตอน/ช่วง เปลี่ยนหน้า และนำ Chunk ไปแก้ไขในช่องข้อความเดิม หรือส่ง Chunk ตรงเข้าคิวเตรียมเสียง โดยใช้ Engine / Voice / Rules / Dictionary / DSP ชุดเดิม
- การ Import ไม่สั่งสร้างเสียงทั้งนิยายอัตโนมัติ และไม่ผูกกับโมเดลใด

## โครงสร้าง

| ไฟล์ | บทบาท |
|---|---|
| src/voxweavetts/document_reader.py | Normalize, Markdown Cleanup, Chapters, Chunking, Paging และ Content Hash โดยใช้ Python Stdlib |
| src/voxweavetts/server.py | POST /v1/documents/preview |
| web/index.html | Local File Picker, เลือก Encoding, Chapter, Chunk และเชื่อม Speech Queue |
| src/voxweavetts/processing.py | กฎ Replacement/Pronunciation/Silence ใช้กับ Chunk เหมือนข้อความปกติ |
| src/voxweavetts/speech_coordinator.py | รับ Chunk เข้าคิวโดยเลือก Engine ใดก็ได้ที่พร้อม |
| tests/test_document_reader.py | Unit Tests, HTTP Tests, End-to-end Mock WAV |

## API

POST /v1/documents/preview

ตัวอย่าง Request Body:

    {
      "title": "Novel.md",
      "format": "md",
      "text": "# บทที่ 1\nชายหนุ่มเป็นอมตะ\n## บทที่ 2\nเซียนเดินทางต่อ",
      "chunk_chars": 350,
      "page_size": 15,
      "page_index": 0
    }

คืนค่า schema_version=1, document_id (SHA256 ของ Format + Normalized Text), title, format, normalized_characters, chapter_total, chunk_total, chunk_chars, page_index, page_size, has_next, chapters[] และ chunks[] ของหน้าที่เลือก

แต่ละ Chunk มี index, chapter_index, chapter_title, start, end และ text

**Offset อยู่ในข้อความที่ Normalize แล้ว ไม่ใช่ Byte Offset ต้นฉบับ**. การเปลี่ยนหน้าใหม่จาก Browser จะส่งเอกสารให้ API อีกครั้งเพื่อคำนวณ Chunk/Paging แบบ Deterministic โดยไม่เก็บข้อความทั้งเล่มไว้บน Server

## เครื่องหมายพิเศษและ JSON สำหรับคำอ่าน

TXT/Markdown รองรับตัวอักษร Unicode, เครื่องหมายคำพูด, สัญลักษณ์, Emoji และวรรณยุกต์ไทย; การตัด Chunk จะพยายามไม่แยก Grapheme Sequence ที่พบบ่อย เช่น Emoji ที่มี Zero-Width Joiner หรือ Skin Tone แต่ไม่รับประกันว่าการแบ่งกลุ่ม Unicode ซับซ้อนทุกแบบจะสมบูรณ์ และการอ่านออกเสียงยังขึ้นกับ Engine

**JSON ที่ใช้แก้กฎคำอ่าน** คือช่อง Rules/Pronunciations ในหน้าเว็บเดิม ไม่ใช่ไฟล์เอกสารสำหรับ Import. มีปุ่มจัดรูปแบบ ตรวจไวยากรณ์ ดาวน์โหลด และเพิ่มรายการที่ Escape อักขระพิเศษให้ ดู [คู่มือคำอ่าน JSON](PRONUNCIATION_JSON_TH.md)

## ความปลอดภัยและ Limits

- รับข้อความไม่เกิน 300,000 ตัวอักษร, HTTP JSON ไม่เกิน 1,250,000 Bytes; UI เปิดไฟล์ไม่เกิน 1 MB
- ไม่เกิน 500 Chapters, 2,500 Chunks, 1–30 Chunks ต่อหน้า (เริ่มต้น 15)
- ปฏิเสธ Format ที่ไม่ใช่ txt/md, ข้อความ Binary/Null, Size/Offset ที่ผิดรูปแบบ
- Frontend แสดงเนื้อหาใน textContent/value เท่านั้น ไม่แทรก HTML ของไฟล์เข้าหน้าเว็บเพื่อรัน Script
- เซิร์ฟเวอร์ไม่เปิด Local File Path และไม่บันทึกเนื้อหาที่ผู้ใช้ Import ลง Disk/Repo; เอกสารอยู่ในหน่วยความจำของ Browser ขณะเปิดหน้า
- Markdown parser เป็น Subset สำหรับข้อความบรรยาย ไม่ใช่ Markdown Renderer สมบูรณ์ Nested Markdown/ตารางซับซ้อนอาจต้องปรับปรุงในอนาคต
- ช่วงข้อความอาจยังเกินข้อจำกัด 500 Spoken Characters หลัง Pronunciation Rules ขยายข้อความ; API จะ Validate และแจ้ง Error ตามจริง
- ยังไม่มี Resume Position ข้าม Session และยังไม่ได้อ่านนิยายแบบต่อเนื่องโดยอัตโนมัติ
- สิทธิ์ใช้ข้อความในนิยายเป็นคนละเรื่องกับสิทธิ์ของ TTS Engine: ดู [Commercial Policy](COMMERCIAL_LICENSE_POLICY_TH.md)

## การตรวจสอบ

มี Unit/HTTP Tests สำหรับ TXT/Markdown Chapter, Code/URL Filtering, Stable Paging/Hash/Offsets, การไม่ทำให้วรรณยุกต์ไทยแยกจากตัวอักษร, Limits/Invalid Inputs และการนำ Chunk ผ่าน Text Processor เข้าคิว Mock Speech Engine เพื่อสร้าง WAV โดยไม่ต้องใช้ ONNX หรือ PyTorch

## วิธีทดลอง

1. เปิด Start-Dev.cmd แล้วเข้า http://127.0.0.1:8765/
2. เลือกไฟล์ .txt หรือ .md พร้อม Encoding UTF-8/Windows-874 ในแผง **นำเข้าเอกสาร TXT / Markdown**
3. กด **เปิดและแบ่งช่วง** แล้วเลือก Chapter/Chunk หรือเปลี่ยนหน้า
4. กด **นำช่วงนี้ไปแก้ไขในช่องข้อความ** เพื่อแก้ Rules/Pronunciation หรือกด **ส่งช่วงนี้เข้าคิวเสียง** ทันที
5. ดูสถานะ/ดาวน์โหลด WAV ที่แผง Speech Queue (สถานะ ready = สร้างไฟล์เสร็จ ยังไม่ใช่จังหวะการเล่นจริง)

## ตำแหน่งอ่านค้างและการอ่านต่อเนื่อง (เพิ่มใน v0.3.0.dev3)

- กด **จดตำแหน่งช่วงนี้** เพื่อบันทึกให้ช่วงที่เลือกเป็นช่วงที่จะอ่านต่อ
- เมื่อเปิดไฟล์เดิมซ้ำ กด **ไปยังตำแหน่งที่อ่านค้าง** (Document Hash, จำนวนช่วง และขนาดช่วงต้องตรงกัน) เพื่อเลือกช่วงนั้น
- กด **สร้างเสียงและอ่านช่วงที่เลือก** เพื่อส่งช่วงนี้ไปที่ Speech Coordinator และเล่น WAV ผ่าน Browser เมื่อพร้อม; ใช้ **พัก / เล่นต่อ** หรือ **หยุดอ่าน**
- เปิดตัวเลือก **อ่านช่วงถัดไปอัตโนมัติหลังเสียงจบ** เพื่อให้ระบบสร้างเสียงเพียงช่วงถัดไปหลัง Browser แจ้งว่าเสียงช่วงปัจจุบันเล่นจบแล้ว โดยมีเพียงหนึ่งช่วงที่กำลังสังเคราะห์ในแต่ละครั้ง; หาก Browser บล็อก Auto-play จะต้องกด Play เอง
- กด **ล้างตำแหน่งที่จำ** เพื่อคืนเอกสารนี้เป็นสถานะไม่มีตำแหน่งที่บันทึก โดยไม่ลบเอกสารบนเครื่อง

Progress เก็บใน `data/reading/positions.json` ซึ่งอยู่ใน Git Ignore โดยมีเฉพาะ SHA256 Document ID, Chunk Size, Chunk Count, Next Chunk Index และ Timestamp ไม่มีข้อความนิยาย ชื่อไฟล์ Path หรือ WAV ของผู้ใช้ ส่วนเนื้อเรื่องต้องเปิดไฟล์ใน Browser ใหม่ทุก Session

API: GET /v1/reading/progress?document_id=<SHA256>, POST /v1/reading/progress (Intent: save-reading-progress), POST /v1/reading/progress/clear (Intent: clear-reading-progress). ใช้ revision แบบ Optimistic Concurrency ป้องกันการบันทึกทับกันจากสองแท็บ และ Atomic Write ป้องกันไฟล์ค้างจากการเขียนไม่ครบ

**ข้อจำกัด:** ถ้าเปลี่ยนขนาด Chunk หรือแก้ข้อความนิยาย Hash/Chunk Mapping อาจเปลี่ยน ทำให้ต้องเลือกตำแหน่งอีกครั้ง; ยังไม่รองรับข้ามเครื่อง ข้าม Browser ในการเล่นเสียงจริง และไม่มี Playback Clock/OBS Subtitle Sync. การกดหยุดระหว่างสร้างเสียงไม่หยุด Model Inference กลางคัน แต่ยกเลิกผลลัพธ์ที่มาภายหลังได้

## Subtitle จากเวลาเล่นจริงใน Browser

เมื่ออ่านนิยายเสียง สามารถดู Subtitle ของช่วงที่เสียงกำลังเล่นใน Document Reader และเปิด http://127.0.0.1:8765/overlay ใน OBS ได้กับทุก Engine. Caption เลือกจากเวลาที่ Browser รายงานด้วย audio.currentTime ทุกประมาณ 250 ms และซ่อนเมื่อหยุด/พัก/จบ หรือ Player ขาดการติดต่อ. เป็น Subtitle ระดับ Segment ยังไม่แยกตรงรายคำ. ดู [Playback/OBS Guide](PLAYBACK_OVERLAY_TH.md)

## Subtitle แบบสตรีมมิงและการแบ่งช่วงข้อความทดลอง

Reader ส่ง Audio Browser Clock ไป Subtitle Relay เดิม แต่ OBS Overlay รับการเปลี่ยนแปลงด้วย SSE ที่ `/v1/playback/stream` ได้แล้ว (HTTP Polling สำรองเมื่อขาดการเชื่อมต่อ) ส่วนโหมด `/overlay?mode=estimated` จะตัดข้อความยาวออกเป็นช่วงที่รักษาวรรณยุกต์ไทยและ Emoji แต่ **คาดเดาเวลาแสดงจากสัดส่วนข้อความเท่านั้น** ไม่ใช่การวิเคราะห์เสียงจริง ดู [PLAYBACK_OVERLAY_TH.md](PLAYBACK_OVERLAY_TH.md)

## งานต่อไป

1. บันทึก Resume Position / Reading Session แบบไม่เก็บเนื้อหาเอกสารซ้ำ
2. Read-Ahead Queue ทีละช่วง พร้อม Backpressure และยกเลิกได้
3. Audio Playback Clock จริง, Pause/Resume, Subtitle Sync
4. รองรับ TXT/Markdown ซับซ้อนขึ้น และ Regression Corpus ภาษาไทย
5. พัฒนา Engine Adapter สำหรับโมเดลฝึกเองเมื่อ Core พร้อม