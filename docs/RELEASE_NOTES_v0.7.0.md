# VoxWeaveTTS v0.7.0 — AI Tool Calling & Search Providers (Windows Portable)

**Release date:** 14 พฤศจิกายน 2026  
**Release type:** Stable feature release; follows v0.6.0.  
**Focus:** เพิ่มการเรียกเครื่องมือแบบอ่านอย่างเดียวภายใต้สิทธิ์ที่ผู้ใช้เปิดจาก Settings และรวมความสามารถทั้งหมดของ v0.6.0

## ความสามารถใหม่ v0.7.0

- **AI Tool Calling แบบ Opt-in**: เริ่มปิดและเปิดใช้ได้เมื่อเลือก Ollama + Custom Prompt เท่านั้น พร้อมแยกสิทธิ์ Wikipedia, ผู้ให้บริการค้นเว็บทั่วไป และการอ่านไฟล์อ้างอิง; จำกัด 1–3 tool calls ต่อข้อความ
- **Web Search Provider Dropdown**: Wikipedia (ไม่ต้องมี API Key), SearXNG (ใช้เซิร์ฟเวอร์ localhost/Private LAN ที่เปิด JSON API), Ollama Web Search (ต้องมีบัญชีและ API Key), Tavily (ต้องมีบัญชีและ API Key/เครดิต)
- **API Key Settings**: บันทึกและลบ API Key สำหรับ Ollama Web Search/Tavily ใน Windows ได้ด้วย **DPAPI แบบผูกกับบัญชีผู้ใช้** เก็บแยกจาก AI Settings, ป้องกันการส่งคีย์กลับผ่าน API, รองรับ Environment Variables `OLLAMA_API_KEY` และ `TAVILY_API_KEY` ถ้าไม่ได้บันทึกในโปรแกรม
- **นำเข้า/ส่งออกโปรไฟล์ค้นหา JSON**: มี Provider, URL SearXNG, ตัวเลือกเปิดใช้ค้นหาเท่านั้น **ไม่รวม API Key หรือ Prompt** เมื่อ import ต้องบันทึก AI Settings เพิ่มเองเพื่อมีผล
- **ปุ่มทดลองค้นหาโดยตรง**: ตรวจ Provider/API ที่บันทึกไว้โดยไม่เรียก Ollama โมเดล แสดงผล 3 รายการ/ครั้ง; บริการ Cloud อาจใช้โควตาจริง
- **File reference tool**: อ่านได้เฉพาะ .txt/.md/.json ที่ผู้ใช้ตั้งพาธไว้ สูงสุด 5 ไฟล์/ไฟล์ละ 16 KiB ตามดัชนี Allowlist; ไม่อนุญาตให้ข้อความจาก Live ระบุพาธใหม่หรือเปลี่ยนสิทธิ์
- **Security limits**: ไม่รัน Shell ไม่เขียน/ลบไฟล์ ไม่เปลี่ยน Settings ไม่เปิด URL ผลค้น ไม่รับโดเมนค้นหาที่โมเดลกำหนดเอง ไม่ตาม HTTP Redirect; หลังอ่านเนื้อหาไฟล์ไม่อนุญาตการค้นเว็บต่อในงานเดียวกัน
- **บันทึกสถานะ/กฎเดิม**: ระบบ TTS, YouTube/Discord/TikTok, Live queue, Subtitle/Overlay, Rules ก่อน-หลัง AI, การแยกชื่อผู้ส่งออกจากการแปล/AI, พจนานุกรมอีโมจิและคำอ่าน ยังคงรองรับตาม v0.6.0

## การทดสอบและการยืนยัน

- Python Unit/Integration ครอบคลุม TTS เดิม, AI Processing, permission deny, tool calls, JSON API Settings, encrypted key storage และการทดสอบ API Mock สำหรับ SearXNG/Ollama Web Search/Tavily
- JavaScript Smoke Tests รวม UI Provider, Key save/clear, profile import/export ที่ไม่มีคีย์, ทดสอบค้นหาตรง, Live/Queue/Overlay และทุกโมดูลเดิม
- เคยทดสอบจริง Ollama `qwen3.5:4b` เรียก Wikipedia Tool Calling และ File Tool กับไฟล์ตัวอย่างได้; อย่างไรก็ตามโมเดล **อาจไม่เรียกเครื่องมือ** แม้เปิดสิทธิ์และ Prompt บอกให้ค้นหา เพราะการเรียกขึ้นกับพฤติกรรมโมเดล
- **การทดสอบ search provider SearXNG, Ollama Web Search, Tavily ในรอบพัฒนานี้ใช้ Mock Responses ไม่ใช่บัญชี/โควตาจริง**; ผู้ใช้สามารถกดปุ่มทดลองค้นหาใน Settings เพื่อตรวจการเชื่อมต่อเอง
- ระบบคำแปล M2M100 418M ยังคงเป็น **Experimental**: เคยผ่านการโหลด/Inference จริง แต่ความหมายผิด 2 ใน 3 ตัวอย่าง; ไม่แนะนำใช้กับ Live ที่ไม่ตรวจสอบคำแปล
- รายการ CI, SHA ของ Release Commit และผล build Portable จาก Tagged Source แสดงในหน้า GitHub Release

## Windows Portable — วิธีเริ่มใช้งาน

1. ดาวน์โหลด `VoxWeaveTTS-v0.7.0-portable.zip`, แตกไฟล์ไปยังโฟลเดอร์ที่ต้องการ
2. เปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd`; เปิดหน้า Web UI ที่ `http://127.0.0.1:8765`
3. ไปที่ **Settings → AI Processing**, เลือก Ollama Engine และโมเดล Ollama ที่ติดตั้งไว้แล้ว (เช่น `qwen3.5:4b`), เลือก **Custom Prompt**, เปิด AI Processing ตามต้องการ
4. เปิด **AI Tool Calling** และเลือกสิทธิ์; สำหรับ **Web Search Provider**, เลือก Wikipedia / SearXNG / Ollama / Tavily และตั้งค่า API Key/URL ตาม Provider
5. กดบันทึก **AI Settings** แล้วใช้ปุ่ม **ทดลองค้นหา** โดยตรง; กดทดลองข้อความ AI แยกเพื่อดูการเรียกเครื่องมือจริง
6. การเปลี่ยนเครื่อง/Windows Account ต้องกรอก API Key ใหม่ เนื่องจาก DPAPI เข้ารหัสผูกบัญชี Windows; การส่งออก JSON **ไม่แนบคีย์**
7. อัปเกรดจากเวอร์ชันก่อน: อย่าลบ/แทนที่โฟลเดอร์ `data/settings`, `data/filters`, `data/dictionaries`, `data/profiles` เดิม โดยปิดโปรแกรมก่อนคัดลอกค่าเข้ารุ่นใหม่

## ไฟล์ที่แนบใน Release — ครบทุกส่วน

| File | Description |
|---|---|
| `VoxWeaveTTS-v0.7.0-portable.zip` | โปรแกรม Windows x64 Portable; self-contained Python + MakHam Paradee ONNX + Web UI, OBS/Live/AI Tool Calling/Docs/Extension source |
| `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip` | Extension อ่านคอมเมนต์ TikTok LIVE ซึ่งยังใช้รุ่นเดิม (ไม่มี Gift speech) |
| `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` | โมเดลเสียงไทย Som เสริม; รายละเอียด License/Attribution อยู่ในแพ็กเกจ |
| `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel` | โมเดลเสียงไทย 4 เสียงเสริม; รายละเอียด License/Attribution อยู่ในแพ็กเกจ |
| `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` | โมเดลแปลภาษาเสริม 418M; **Experimental**; ต้องเตรียม optional PyTorch/Transformers/SentencePiece Runtime เอง |
| `SHA256SUMS-v0.7.0.txt` | SHA-256 ของไฟล์ดาวน์โหลดทั้งห้ารายการข้างต้น |

**หมายเหตุ:** .vwmodel ทั้งสามเป็นไฟล์แยกเพื่อไม่ให้ Windows Portable หลักใหญ่เกินจำเป็น; รุ่นหลัก **ไม่บันเดิล Ollama ตัวโปรแกรม, M2M100 Runtime/Weights, Torch, Transformers, โมเดลเสียงเสริม, บัญชีผู้ใช้ หรือ API Keys**

## สิทธิ์ใช้งานและข้อจำกัด

- โปรแกรม VoxWeaveTTS: MIT; โปรดตรวจ License/Attribution ของโมเดลแต่ละชุดแยกกัน
- MakHam TTS ใน ZIP หลัก: Apache-2.0 ตาม notices ภายในแพ็กเกจ; FastThaiG2P: upstream Apache-2.0 และชุดข้อมูลเสียง Som CC BY 4.0; Vachana: upstream model card declares MIT; M2M100: upstream model card declares MIT; ข้อความเหล่านี้อ้างตามผู้เผยแพร่โมเดล ไม่ใช่การตรวจสิทธิ์ทั้งหมด
- Ollama Web Search อาศัย Cloud API ของ Ollama และบัญชี/API Key ไม่ใช่การค้นแบบ Offline; Tavily อาศัยบริการ Cloud; SearXNG ต้องติดตั้งเองและเปิด JSON API
- ไม่รับประกันความแม่นยำของผลค้นจากอินเทอร์เน็ตหรือคำตอบ AI และไม่รับประกัน Live จาก YouTube/Discord บัญชีจริงทุกสถานการณ์; Prompt Injection ยังเป็นความเสี่ยง
- ไม่รองรับ Voice Cloning, Training, Word-level forced alignment, เครื่องมือ Shell/แก้ไขไฟล์, เปิดหน้าเว็บ/URL ผลค้นอัตโนมัติ

**คู่มือเพิ่มเติม:** `docs/AI_TOOL_CALLING_TH.md`, `docs/M2M100_SETUP_TH.md`, `README_TH.md`, `model-packs/README_TH.md`.
