# VoxWeaveTTS — AI Processing & Translation (ข้อกำหนดที่ตกลงกัน)

สถานะ: **Specification / implementation plan** — ไม่ใช่คำยืนยันว่ามีความสามารถทั้งหมดแล้ว
อ้างอิงโค้ดตั้งต้น: `main` @ `be74e28` (v0.5.2) — 2026-11-14

## วัตถุประสงค์

เพิ่ม AI Processing เป็นส่วนหนึ่งของ **Settings กลางชุดเดียว** ใช้งานร่วมกับทุกโหมด (Studio, Document, YouTube LIVE API/Browser, TikTok LIVE/TikFinity/Extension, Discord Bot/Client และ API) โดยไม่สร้างโหมดใหม่ ไม่เปลี่ยนโครงสร้าง TTS/การคุมเสียงแต่ละโหมดอย่างไม่จำเป็น เริ่มต้น **ปิด** เพื่อคงพฤติกรรมเดิมไว้

ใช้เพื่อแปลข้อความต่างภาษาเป็นภาษาปลายทาง (เลือกได้ ไม่จำกัดไทย), รองรับข้อความหลายภาษาปนกัน และอาจใช้ AI ทำงานตาม Prompt เช่นตอบคำถาม/ค้นข้อมูลจากเครื่องมือที่อนุญาต

## ลำดับข้อความที่เป็นข้อตกลงตายตัว

1. รับข้อความจากแต่ละโหมด โดยเก็บข้อความดิบกับข้อมูลผู้ส่งไว้คนละฟิลด์
2. **กฎ/การจัดการเฉพาะโหมด** ทำก่อน *กฎกลางก่อน AI* เสมอ: กรองแชท, แยกข้อมูล, การแทนอีโมจิเป็นคำอ่าน, จัดการคำนำหน้าชื่อและ @ ตามช่องทาง
3. **กฎกลางก่อน AI (Pre-AI Rules)** ประมวลผลเฉพาะ *เนื้อหาข้อความ* ก่อนส่ง AI
4. **AI Processing**: ตรวจภาษาปลายทาง/ภาษาอื่น, ข้ามแปลเมื่อเหมาะสม, แปลเฉพาะช่วงที่ต่างภาษากลับมารวม หรือส่งทั้งข้อความให้ LLM แปลตามบริบท, หรือประมวลผลตามคำสั่ง AI ที่กำหนดได้ เช่นตอบคำถาม
5. **กฎกลางหลัง AI (Post-AI Rules)** ทำเสมอ แม้ AI ถูกปิด หรือข้ามการแปลเมื่อข้อความมีภาษาปลายทางอยู่แล้ว
6. พจนานุกรมคำอ่านเฉพาะการสังเคราะห์เสียง / Speech Plan / Silence / TTS Engine / Playback Clock และ Overlay APIs โดยไม่ทำให้เวลาซับไตเติลผิด

**ข้อความผู้ส่งไม่ผ่าน AI Translation:** คำนำหน้าชื่อ + ตัวเลือกแสดง/ซ่อน @ + ชื่อผู้ส่ง + คำเชื่อมหลังชื่อผู้ส่งก่อนข้อความ ไม่ส่งเข้า AI และไม่นำไปผ่านกฎกลางก่อน/หลัง AI ให้ประกอบกับเนื้อหาที่ประมวลผลแล้วก่อน TTS ชื่อยังใช้การตั้งค่าเฉพาะโหมด/การแทนอีโมจิในชื่อของโหมดเดิม แสดงต้นฉบับสำหรับ UI/Overlay ได้ ไม่แปลชื่อ/คำเชื่อมโดยปริยาย ถ้าปิดอ่านชื่อ ให้คงชื่อในประวัติแต่ไม่อ่านเสียง

## Settings ส่วนกลาง

- เปิด/ปิด AI Processing ทั่วโปรแกรม (ค่าเริ่มต้นปิด)
- เป้าหมายภาษา (เช่น `th`, `en`, `ja`, `zh`, `ko`) และตัวเลือกตรวจจับภาษา
- วิธีแปล: `foreign_spans` (แปลช่วงต่างภาษาและรวมต้นฉบับ) กับ `whole_message` (แปลข้อความรวมเมื่อพบภาษาอื่น เหมาะกับ LLM)
- **Translation / AI Engine Registry** แยกจาก Voice Engine Registry แต่ใช้แนวคิดเดียวกัน: `EngineInfo` + Adapter Contract + Factory/Registry และ Model Package metadata/weights แบบ data-only. เลือก Engine และโมเดลได้จาก Settings โดยตรวจ runtime/assets/capabilities จริง; สามารถเพิ่ม adapter ใหม่ใน trusted application code และติดตั้ง model weights แยกภายหลังโดยไม่เปลี่ยนเส้นทางประมวลผลหลัก
- Built-in adapters: `Ollama` สำหรับ LLM (ต้องมี Ollama และโมเดลติดตั้งในเครื่อง) และ `M2M100 418M` สำหรับแปลแบบดั้งเดิม (ต้องมี runtime และ weights แยก; ไม่รวมใน Portable ปกติ); แสดงสถานะ `not installed` เมื่อยังไม่พร้อม และไม่ปลอมว่าแปลได้
- M2M100 อ้างอิง `facebook/m2m100_418M` (Hugging Face model card ระบุ MIT); weights ใหญ่ประมาณ 1.9 GB, รองรับหลายภาษาและ `forced_bos_token_id`, ต้องรู้ภาษาต้นทาง (ใช้ตัวเลือกกำหนดเองหรือ detector ที่น่าเชื่อถือเมื่อมี) ไม่รองรับ Priority/Custom Prompt หรือ Tool Calling และไม่สามารถรับประกันการแปลข้อความผสมแบบ LLM. อ้างอิง: https://huggingface.co/facebook/m2m100_418M
- ห้ามติดตั้ง/โหลดหรือรัน Python, DLL, EXE หรือโค้ดที่แนบมากับ package โมเดล; เพียง metadata + weights พร้อมขนาด/Hash/License; Adapter ใหม่เพิ่มจากโค้ดแอปที่ตรวจสอบได้เท่านั้น
- นโยบาย built-in: รวมเฉพาะ adapter ที่ implement และทดสอบได้จริง โดยไม่รวมโมเดลที่ไม่มีสิทธิ์หรือ runtime ที่ยังไม่ผ่าน; แยกคำว่า `Adapter available`, `Model installed`, `Runtime ready`, `Verified inference` ชัดเจน
- **Priority Instructions** (คำสั่งความสำคัญสูงของผู้ใช้) และ **Custom Prompt** (คำสั่งทั่วไป) แยกช่อง เพิ่ม/แก้ไข/บันทึกและทดสอบได้ โดย Priority ชนะเมื่อขัดแย้งกัน
- พรอมต์สำเร็จรูป เช่น เป็นทางการ เป็นกันเอง ตรงตามต้นฉบับ / คำสั่งกำหนดเอง
- ข้อความสำหรับ Overlay/API: ต้นฉบับ / หลัง AI / ทั้งคู่ โดยต้องไม่ปล่อยข้อความที่ถูกกรองออกในเส้นทางที่ควรถูกปิดบัง
- นโยบายเมื่อ AI ไม่พร้อม, หมดเวลา หรือแปลล้มเหลว: ข้าม AI ใช้ข้อความที่กรองแล้ว / ข้ามข้อความ / ลองใหม่ตามเพดาน กำหนด Timeout และ Queue bounded
- มีตัวอย่างผลแต่ละขั้นให้ตรวจโดยไม่ต้องสร้างเสียงจริง
- กฎก่อน/หลัง AI ใช้ระบบ editor เดิม รองรับแยก stage และ Quick Add; รายการเก่าที่ไม่มี stage ต้องไม่เปลี่ยนพฤติกรรม (นับเป็น Post-AI) รองรับเลือก source ตามเดิม; rule modes replace/skip/silence ควรไม่เผลอรั่วข้อความผ่าน AI หรือจอ

## การเลือกโมเดลจากเครื่อง (ไม่มีปุ่มดาวน์โหลด)

- หน้า Settings → AI Processing มีตัวเลือก **ไม่แปล / ไม่เรียก AI**, **แปลภาษา**, **ทำงานตาม Prompt** และรายการ Engine ที่ติดตั้ง/รองรับ
- **Ollama**: พิมพ์ชื่อโมเดลเองได้ (เช่น `qwen3.5:4b`) หรือเลือกจากรายชื่อโมเดลที่ตรวจพบผ่าน Ollama API `GET /api/tags`; ค่าเริ่มต้น `http://127.0.0.1:11434` แต่ให้กำหนดเองเป็น `http://localhost:PORT` หรือ `http://IP_PRIVATE:PORT` บน LAN ได้ โดยไม่มี URL สาธารณะ, path, credential หรือ HTTPS proxy; ต้องบันทึกก่อนสั่งตรวจ/โหลด; การพิมพ์/บันทึกชื่อจะไม่ `pull` หรือ `download` โมเดลใด
- ปุ่ม **ตรวจสอบโมเดล** เรียก API ของปลายทางที่บันทึกไว้ ดูโมเดลที่ติดตั้งและ `GET /api/ps` ดูที่กำลังอยู่ใน RAM/VRAM; ค่าตั้งต้นไม่บังคับ fixed URL ไปยัง localhost เมื่อเชื่อมเครื่องอื่น
- ช่อง **Keep Alive (นาที)** กำหนดค่าได้ 1–360 (ค่าเริ่มต้น 360) ใช้กับทั้งการ Preload และ `POST /api/chat` จริง; ปุ่ม **โหลดโมเดลเข้าหน่วยความจำ** ทำงานต่อเมื่อผู้ใช้กดจริงและโมเดลปรากฏในรายชื่อที่ติดตั้งแล้วเท่านั้น ใช้ `POST /api/generate` กับ prompt ว่าง, ไม่ดาวน์โหลด/ติดตั้งและไม่เปิด shell. Ollama อาจใช้ RAM หรือ VRAM ตามฮาร์ดแวร์และ runtime
- **ไฟล์อ้างอิง**: ใส่พาธเต็มหลายรายการคั่นด้วย `,` หรือขึ้นบรรทัดใหม่ได้ (แปลงเป็น array ใน JSON Settings), จำกัดไม่เกิน 5 ไฟล์/ไฟล์ละ 16 KiB (`.txt`, `.md`, `.json`); เปิดสิทธิ์อ่านไฟล์ด้วยตัวเลือกเฉพาะเอง
- **M2M100**: Adapter และ Model Registry เป็นโมดูลแยกจาก Ollama; โมเดลน้ำหนักไม่รวมกับ Portable หลัก ต้องมีไฟล์โมเดลที่ติดตั้งไว้ในเครื่องและ runtime `torch/transformers/sentencepiece/safetensors` ก่อน โดยเลือกโมเดลจากรายการ AI Packages ที่ตรวจพบ หรือใช้โฟลเดอร์ `models/ai/m2m100_418m` ที่เตรียมไว้; ไม่มีปุ่มดาวน์โหลด/ติดตั้งโมเดลใน AI Settings
- การมีชื่อโมเดลในรายการไม่เท่ากับการทดสอบ Inference ผ่านจริง: UI แยก Installed, Runtime Ready, In Memory จากผลทดสอบจริง
- **ผลทดสอบ Ollama จริง 2026-11-14**: ด้วยโมเดล `qwen3.5:4b` ในเครื่อง ผ่านการแปลสั้น 6 กรณี: อังกฤษ→ไทย, ไทย→อังกฤษ, ไทย/อังกฤษผสม→ไทย, อังกฤษ→ญี่ปุ่น, อังกฤษ→จีน, อังกฤษ→เกาหลี (`tests/verify_live_translation.py`). เป็นเพียง functional smoke test ยังไม่รับรองความแม่นยำทุกประเภทข้อความ
- ปัจจุบันการเรียก AI Translation ใน Backend ยังทำระหว่างการเตรียมงานผ่าน HTTP Request; **ยังไม่ใช่ asynchronous AI queue** และยังไม่ได้ทดสอบ M2M100 กับน้ำหนักโมเดลจริงหรือทดสอบเส้นทาง Live แบบโหลดสูง จึงยังไม่ควรถือว่าพร้อมสำหรับ Live ยาว ๆ
- มี UI สำหรับจัดการ Model Packages ของ **TTS เดิม** แยกต่างหากตามพฤติกรรมเดิม ไม่เกี่ยวกับการดาวน์โหลด AI Model
- หลักฐานวิธีโหลด Ollama: https://github.com/ollama/ollama/blob/main/docs/api.md (การส่ง prompt ว่าง / keep_alive)
- แหล่ง M2M100: https://huggingface.co/facebook/m2m100_418M (Model Card ระบุ MIT) แต่ไฟล์ใน repo อย่างเป็นทางการขณะตรวจสอบมี `pytorch_model.bin` ไม่ใช่ `model.safetensors`; Adapter นี้ **ตั้งใจไม่โหลดไฟล์ pickle/bin เพื่อความปลอดภัย** ต้องเตรียม safetensors ที่แปลงและตรวจสอบจากแหล่งที่เชื่อถือได้ไว้ในเครื่องก่อนใช้งานจริง ยังไม่ได้ทดสอบ Inference ด้วยน้ำหนัก M2M100 บนเครื่องนี้ จึงต้องรายงานสถานะ Not Ready ตามจริง

## Trust Boundary และ Tool Calling

- ข้อความที่เข้ามาจากแหล่งภายนอกเป็น **ข้อมูลเท่านั้น** แม้มีคำสั่งหรือข้อความล่อโมเดล ก็ไม่มีสิทธิ์ควบคุมการทำงาน ไม่สามารถเปลี่ยน Priority/Custom Prompt/Settings/Tool Permissions
- คำสั่งของแอปพลิเคชัน > Priority Instructions ของผู้ใช้ > Custom Prompt > ข้อความภายนอก (data only)
- แยก role/ช่องข้อมูลที่เชื่อถือได้จากเนื้อหาที่แปลอย่างชัดเจน และตรวจสอบผลลัพธ์ก่อนส่งต่อ; ไม่มีระบบ prompt-only ที่รับประกันต้าน prompt injection 100%
- Tool Calling เป็นสิทธิ์เพิ่มต่างหากจากพรอมต์; เริ่มจากปิดโดยปริยาย บังคับใช้ whitelist และขอบเขตจริงโดย Backend ไม่ใช่หวังจากคำสั่ง AI:
  - อ่านไฟล์: จำกัด path ที่ผู้ใช้ระบุ, read-only, จำกัดขนาด, ไม่เปิดเผย path/content ในเสียงถ้าไม่ได้รับอนุญาต
  - ค้นเว็บ: opt-in แยก, จำกัดปลายทาง, timeout, จำนวนครั้งต่อข้อความ, ไม่อนุญาตการเขียน/ส่งโพสต์
  - ไม่เปิด shell, เขียนไฟล์, อ่านไฟล์ทั่วไดรฟ์, แก้ Settings หรือเรียกใช้เครื่องมืออันตรายผ่านข้อความแชท
- หลีกเลี่ยงการส่งข้อมูลส่วนตัวไป Cloud โดยไม่แจ้งให้ทราบ; ระบบ Local เป็นค่าเริ่มต้น

## สัญญาข้อมูลภายใน

เก็บอย่างน้อย:
- `source`, `source_message_id`, `sender.original`, `sender.spoken`, `sender.prefix`, `sender.at_option`, `sender.separator`
- `original_text` (immutable), `mode_processed_text`, `pre_ai_text`, `ai_result_text`, `post_ai_text`, `speech_text`, `display_text`
- `ai_applied`, `language_detected`, `target_language`, `processing_status`, `warnings`
- Display เลือกข้อความต้นทาง/หลัง AI/คู่ โดยแยกจาก `speech_text` และไม่รั่วกฎกรองที่ตั้งใจให้ปิดบัง

## จุดเชื่อมในโค้ดจริง v0.5.2

- `web/mode_inputs.js` ฟังก์ชัน `speechText()` ปัจจุบันรวมชื่อผู้ส่งและแทนอีโมจิก่อน `POST /v1/jobs`; จะต้องเปลี่ยนเป็นส่ง metadata ผู้ส่งแยกก่อนประกอบทีหลัง
- `src/voxweavetts/server.py` เมธอด `_text_plan` เป็นจุดเชื่อม Backend สำหรับ `/v1/jobs`, `/v1/text/process`, `/v1/speech`
- `src/voxweavetts/processing.py` แยก `spoken_text` กับ `display_text` และ `segments`; ต้องไม่สูญเสีย semantics ของ skip/silence เมื่อแทรก AI
- `src/voxweavetts/text_settings.py` มี atomic JSON save + optimistic revision; ต้อง migrate กฎเดิมโดยไม่ทำลายไฟล์เดิม
- `src/voxweavetts/speech_coordinator.py` ใช้คิวสร้างเสียงที่รับแผนข้อความพร้อมแล้ว ไม่ควรบล็อก HTTP รอค้นเว็บ/LLM นาน ๆ; ต้องแยก asynchronous AI preparation ออกจาก synthesis queue เมื่อเปิด AI

## ลำดับพัฒนาและเกณฑ์ยอมรับ

1. ออกเอกสารข้อกำหนดนี้ก่อนแก้โค้ดและตรวจสถานะ Git; ห้ามทำ release โดยไม่ได้รับคำสั่ง
2. ทำ Config + Rules stage + Migration โดย AI default off: พิสูจน์ผ่าน regression tests ว่าเก่าทำงานเท่าเดิม
3. ทำโมดูล AI Processing + LLM Adapter ที่แยกบทบาท Priority/Custom Prompt และ external input, มี timeout/fallback, หลักฐานทดสอบ mock
4. เชื่อม API / frontend ทุกโหมดให้มี sender metadata แยกจากข้อความ และเพิ่ม Settings/Preview/Overlay selection
5. รองรับ Tool Calling แบบปิดเริ่มต้นและทดสอบ permission gating ก่อนเปิดใช้จริง
6. ทดสอบ Python/Node smoke, อัปเดตคู่มือ/README ให้แสดงสิ่งที่เสร็จและยังไม่เสร็จ, จบด้วย Git status ตามจริง; publish/release เฉพาะเมื่อร้องขอ

หลักสำคัญ: เอกสารแผนไม่ใช่คำยืนยันว่าระบบนั้นพร้อมใช้งานแล้ว และการเลือกวิธี implementation ต้องรักษาเวอร์ชัน Portable, JSON เดิม และ Offline default โดยไม่เสียพฤติกรรม TTS ที่ผู้ใช้ทดสอบแล้ว