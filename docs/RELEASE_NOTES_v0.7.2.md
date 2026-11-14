# VoxWeaveTTS v0.7.2 — แก้การหยุดอ่านแชทเมื่อหน้าเว็บหลักอยู่เบื้องหลัง

**Release:** 14 พฤศจิกายน 2026 · Windows x64 Portable · Patch update ต่อจาก v0.7.1

## สิ่งที่เปลี่ยนใน v0.7.2

- **Server-Sent Events (SSE):** Python Backend ส่งสัญญาณเมื่อมีข้อความใหม่เข้าหน้าเว็บหลัก `http://127.0.0.1:8765` แทนการรอ `setInterval` อย่างเดียว
- **Multiplexed SSE:** ใช้หนึ่งการเชื่อมต่อร่วมกันระหว่างแหล่ง YouTube/Discord/TikTok ที่กำลังเปิด โดยมีสถานะ/Revision แยกกัน ลดปัญหาจำนวน Connection ของเบราว์เซอร์เต็ม
- **ความเป็นส่วนตัว:** SSE แจ้งเพียงโหมด สถานะ หมายเลขการเปลี่ยนแปลง และจำนวนข้อความค้าง ไม่ส่งข้อความแชทหรือคีย์; การดึงข้อความจริงยังต้องมี Owner Token ผ่าน POST `/v1/sources/drain`
- **รอเสียงโดย Backend:** การอ่าน Live, Studio, Document และ Queue ใช้ GET `/v1/jobs/{speech_id}?wait=1` เพื่อรอผล AI/TTS โดยไม่ใช้ Timer ของแท็บที่ซ่อน
- **OBS/Subtitle:** ส่งสถานะเวลาเสียงจริงผ่าน Media `timeupdate` เพิ่มจาก Timer สำรอง
- **Fallback/Recovery:** เมื่อ SSE ขาดการเชื่อมต่อใช้ Polling สำรอง และเมื่อหน้าเว็บกลับมาอยู่ด้านหน้าจะตรวจคิวทันที; จำกัดจำนวน SSE Subscribers/Job Waiters และคงมาตรการ Queue Overflow

## ความสามารถเดิมที่ยังอยู่ครบ

- **YouTube LIVE (Browser):** จาก v0.7.1 มีการสลับ Top chat → Live chat อัตโนมัติ ลด Background Throttling ของหน้าต่าง YouTube แยก และแจ้งสถานะหน้าต่าง
- **Live Readers:** YouTube API, TikTok ผ่าน TikFinity/Extension, Discord Bot และ Discord Client, อ่านชื่อผู้ส่ง/อีโมจิ กฎกรองคำและแทนคำ
- **TTS:** MakHam Paradee ONNX ใน ZIP หลัก, อ่านเอกสาร, Studio, ปรับเสียง/ความเร็ว, Pronunciation Dictionary, API และ OBS Overlay
- **AI:** Ollama/M2M100 Experimental, Prompt/Priority Instructions, แปลภาษา, Keep Alive, Pre/Post-AI Rules
- **AI Tool Calling:** เปิดแยกเอง; Wikipedia, SearXNG, Ollama Web Search, Tavily, อ่านไฟล์ Allowlist, จัดการ API Key แบบ DPAPI และโปรไฟล์ JSON

## ดาวน์โหลดครบ 6 ไฟล์

| Release asset | รายละเอียด |
|---|---|
| `VoxWeaveTTS-v0.7.2-portable.zip` | Windows Portable พร้อม EXE, Python Runtime, MakHam ONNX, Web UI, Extension source, Source SSE, AI และ Docs |
| `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip` | TikTok LIVE Extension รุ่นเดิม ตรวจ SHA-256 ก่อนแนบ |
| `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` | โมเดลเสียง ThaiSom เสริม พร้อมเอกสาร License/Attribution |
| `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel` | โมเดล Vachana Thai 4 เสียง เสริมพร้อม License/Attribution |
| `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` | โมเดลแปลภาษาเสริม 418M **Experimental**; ต้องเตรียม Runtime เพิ่มเอง |
| `SHA256SUMS-v0.7.2.txt` | SHA-256 ของไฟล์ดาวน์โหลดทั้งห้า |

**หมายเหตุ:** โมเดลเสริมทั้งสามเป็นไฟล์ดาวน์โหลดแยก; ไม่รวม Ollama executable, PyTorch/Transformers, API Keys หรือข้อมูล Settings ส่วนตัวใน Portable หลัก

## วิธีติดตั้ง/อัปเกรด

1. ปิด VoxWeaveTTS รุ่นเก่าและสำรอง `data/settings`, `data/filters`, `data/dictionaries`, `data/profiles`, `models/packages` และโมเดล AI ที่ติดตั้งเอง
2. แตก `VoxWeaveTTS-v0.7.2-portable.zip` ลงโฟลเดอร์ที่เขียนได้ แล้วเปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd`
3. เปิดหน้า `http://127.0.0.1:8765`; เข้า YouTube LIVE (Browser) เพื่อเชื่อมต่อและเปิด Auto Read ตามต้องการ
4. ตรวจสถานะ **รับข้อความแบบ Server Push**; หาก SSE ไม่พร้อมจะใช้ **Polling สำรอง**
5. ติดตั้ง `.vwmodel` ผ่านตัวจัดการ Model Packages; สำหรับ M2M100 ให้ทำตาม `docs/M2M100_SETUP_TH.md` เนื่องจากต้องเตรียม Runtime เพิ่ม
6. ทดสอบไลฟ์จริงโดยสลับหน้าเว็บหลักไปเบื้องหลัง ตรวจจำนวนข้อความที่รับ, คิวเสียง และ Subtitle; ตรวจ Browser Autoplay หากมีข้อความเข้าแต่เสียงไม่ออก

## ข้อจำกัดและการทดสอบ

- มี Automated Tests สำหรับ SSE แบบแบ่งโหมด, Hidden Tab ไม่ใช้ Timer, Source Token/Queue, Job Waiting, Subtitle timeupdate และระบบเสียง/AI เดิม
- **ยังไม่ได้ตรวจ YouTube LIVE จริงโดยย่อหน้าต่างเป็นเวลานาน**: หากเบราว์เซอร์/Windows Freeze หรือ Discard ทั้งหน้า JavaScript และ HTMLAudioElement ยังหยุดได้; SSE ไม่รับประกันการเล่นเสียง 100%
- M2M100 ยังเป็น Experimental: เคยพบผลแปลผิดความหมายใน 2 จาก 3 ตัวอย่าง ไม่เหมาะสำหรับ Live ที่ไม่มีผู้ตรวจ

## เอกสาร

`README_TH.md`, `README.md`, `docs/PORTABLE.md`, `docs/MAIN_BROWSER_BACKGROUND_TH.md`, `docs/YOUTUBE_BROWSER_READER_TH.md`, `docs/AI_TOOL_CALLING_TH.md`, `docs/M2M100_SETUP_TH.md`

**License:** แอป MIT; ตรวจ License/Attribution ของแต่ละโมเดลและข้อมูลฝึกเพิ่มเติมตามเอกสารในแพ็กเกจ
