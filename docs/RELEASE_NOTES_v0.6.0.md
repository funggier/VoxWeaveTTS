# VoxWeaveTTS v0.6.0 — AI Processing / Translation (Windows Portable)

**วันที่:** 14 พฤศจิกายน 2026
**สถานะ:** Release preparation; ต้องยืนยัน GitHub Release/Assets/CI หลังเผยแพร่
**ขอบเขต:** post-v0.5.2 / pre-AI Tool Calling

## เพิ่มในรุ่นนี้

- Settings กลาง **AI Processing** แบบ opt-in โดยเริ่มปิด: โหมด ไม่แปล/ไม่เรียก AI, แปลภาษา, Custom AI Processing พร้อม Priority Instructions, Custom Prompt, ภาษาปลายทางไทย/อังกฤษ/ญี่ปุ่น/จีน/เกาหลี หรือไม่ระบุให้ Ollama ใช้ภาษาใน Prompt
- เมื่อเลือกภาษาปลายทางชัดเจนในโหมดแปล ค่านั้นมาก่อนภาษาที่สั่งใน Prompt; เมื่อเลือกไม่ระบุให้ Priority Instructions > Custom Prompt; M2M100 + ไม่ระบุ = ข้ามแปลทันที
- Ollama Model พิมพ์เองหรือเลือกจากที่ติดตั้งในเครื่อง, ตั้ง IP/Port ภายใน LAN, Keep Alive และปุ่มโหลดโมเดลเข้า RAM/VRAM แบบกดเอง โดย **ไม่มีการดาวน์โหลด/ติดตั้งโมเดลอัตโนมัติ**
- ไฟล์อ้างอิงที่ผู้ใช้อนุญาตให้ AI อ่าน เป็น .txt/.md/.json สูงสุด 5 ไฟล์ แยกพาธด้วยจุลภาคหรือขึ้นบรรทัดใหม่ อ่านอย่างเดียว ปิดโดยค่าเริ่มต้น
- ระบบกฎก่อน/หลัง AI; กฎเก่าคงเป็นหลัง AI, ชื่อผู้ส่ง+คำนำหน้า+การแสดง @+คำเชื่อมถูกเก็บแยกจากเนื้อหาที่ส่งแปล; อีโมจิแทนคำตามโหมดก่อนเข้า AI
- Asynchronous AI preparation queue แยกจาก TTS, สถานะ preparing/queued/rendering/ready, คิวมีขอบเขต, cancel/dedupe/backpressure, terminal skipped เมื่อกรองข้อความทั้งหมด; Live reader ข้ามข้อความแล้วไปต่อไม่ปิด auto-read
- โมดูล Adapter AI แยกจาก TTS มี Ollama และ M2M100 (experimental); รองรับโมเดล data-only ที่ติดตั้งเองในโฟลเดอร์และไม่มีการ execute โค้ดจากโมเดล

## หลักฐานตรวจสอบ

- Python Unit/Integration tests และ JS smoke ครอบคลุมระบบเดิมและ AI/Live queue ใหม่ ใช้การส่งข้อความจำลองและข้อจำกัดคิว 12 งาน; สถานะขั้นสุดท้ายตรวจสอบใน CI และ release record
- Real Ollama model `qwen3.5:4b` ทดสอบแปลข้อความสั้น 6 กรณี (ไทย อังกฤษ ญี่ปุ่น จีน เกาหลี และข้อความผสม) และ Prompt Language precedence 3 กรณี ทดสอบในเครื่องจริงก่อนเผยแพร่
- Real M2M100 418M ทดสอบด้วย `model.safetensors` จาก official repository revision `1fa802356610a66e78d152c9f4a16206f88315e5`, SHA-256 `c061a21eec15453944783ceb4a13a216477dd4765c98fac10811818adf994968`: โหลด/Inference ได้จริง แต่ **semantic quality FAIL 2/3** (ภาษาอังกฤษ→ไทย และอังกฤษ→ญี่ปุ่น) จึงต้องถือเป็น **EXPERIMENTAL** ไม่ควรใช้กับ Live โดยไม่มีคนตรวจ
- เครื่องหมาย PASS ของภาษาที่เลือกไม่ใช่หลักฐานว่าความหมายถูกทุกประโยค; ไม่รับรองความแม่นยำของ LLM/M2M100 ในทุกภาษา

## การติดตั้งและข้อจำกัด

- Portable หลักมี Python runtime, Web UI, MakHam Paradee ONNX, Launcher, DOCS, OBS, Live และ AI code. **ไม่บันเดิล Ollama, AI weights, Torch, Transformers** และไม่เปิดใช้งาน AI โดยปริยาย; รุ่นหลักไม่มีปุ่มดึงโมเดล AI มาใหม่
- ผู้ใช้ที่มี Ollama ในเครื่องอยู่แล้วสามารถพิมพ์ชื่อ Model ใน Settings; สามารถชี้บริการ Ollama ใน private LAN แต่ต้องตระหนักว่าข้อความแชทจะถูกส่งไปยังเครื่องนั้น
- M2M100 ต้องมี weights + optional runtime ผู้ใช้ติดตั้งเอง; ดู [คู่มือ](M2M100_SETUP_TH.md). หากไม่มี จะมีสถานะไม่พร้อม แต่ TTS และ Ollama ไม่ได้รับผลกระทบ
- YouTube LIVE / Discord Bot ไม่ได้ทดสอบกับ Live account ที่ได้รับอนุญาตครบทุกสถานการณ์; offline mocked integration/queue tests เท่านั้น จึงไม่รับประกันความคงทนของแพลตฟอร์มจริงหรือสิทธิ์ API
- Subtitle จาก speech-plan / WAV timing ยังไม่ใช่ forced word alignment
- AI Tool Calling, web search, file-tool execution, arbitrary shell/tool invocation **ไม่รวมใน v0.6.0**; จะกลับมาพัฒนาต่อเฉพาะหลังปล่อย Release นี้

## ผู้ใช้งานเดิม

- Settings AI ใหม่เริ่มปิด; Rules เดิมที่ไม่มี `stage` ถูกตีความเป็น post-AI จึงไม่เปลี่ยนลำดับเมื่อยังไม่เปิด AI
- หลีกเลี่ยงการลบ `data/settings`, `data/filters` และ `data/profiles` ของผู้ใช้เดิม; ไม่บันเดิลการตั้งค่าส่วนตัวใน ZIP

## GitHub Release artifacts ที่ตั้งใจเผยแพร่

- `VoxWeaveTTS-v0.6.0-portable.zip`
- `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip` (ตัวเดิมที่รองรับคอมเมนต์)
- `SHA256SUMS-v0.6.0.txt`

ทั้งหมดจะตรวจ SHA256 และ exact tag commit หลังอัปโหลด; เอกสารนี้ไม่ใช้แทนการยืนยันว่า Release ถูกสร้างขึ้นแล้ว