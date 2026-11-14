# VoxWeaveTTS v0.7.1 — YouTube Live chat / Background Reliability

**วันที่:** 14 พฤศจิกายน 2026 | **ประเภท:** Patch Release สำหรับ Windows Portable ต่อจาก v0.7.0

## สิ่งที่เพิ่มและปรับปรุง

1. **YouTube LIVE (Browser) เปลี่ยน Top chat → Live chat อัตโนมัติ** — เมื่อพบเมนูตัวเลือกแชท โปรแกรมพยายามเลือก Live chat ซึ่งไม่กรองข้อความแบบ Top chat และรอสลับสูงสุดประมาณ 12 วินาทีก่อนเริ่มเก็บข้อความใหม่ ไม่อ่านประวัติเดิมหรือข้อความซ้ำ
2. **ลด Background Throttling ของหน้าต่าง Chrome/Edge ที่ VoxWeaveTTS เปิดเอง** — ใช้ Chromium flags สำหรับ background timer, occluded windows, renderer backgrounding และ native occlusion รวมกับ Chrome DevTools Protocol Focus Emulation / Active Page Lifecycle โดยไม่แย่งโฟกัสหรือเปลี่ยนการตั้งค่าเบราว์เซอร์ส่วนตัวของผู้ใช้
3. **เพิ่มสถานะใน UI** — แสดง Live chat / Top chat / กำลังเปลี่ยน / ยืนยันไม่ได้ และสถานะ Page Visibility เมื่อหน้าต่างอยู่เบื้องหลัง; หาก YouTube เปลี่ยนหน้าเว็บจนสลับไม่ได้ โปรแกรมจะรายงานสถานะและยังพยายามอ่านต่อ

**ข้อจำกัด:** ผ่านการทดสอบ Chrome/CDP จริงด้วยหน้า HTML จำลองซึ่งสามารถสลับ Top → Live ได้ แต่ยังไม่ได้ทดสอบยาวกับ YouTube LIVE จริงขณะย่อหน้าต่าง YouTube อาจเปลี่ยน DOM หรือหยุดส่งข้อมูลเอง จึงยังไม่รับรองว่าอ่านได้ต่อเนื่องทุกกรณี

## รวมทุกความสามารถจากรุ่นก่อน

- TTS ภาษาไทย MakHam Paradee ONNX พร้อมพจนานุกรมคำอ่าน เสียง/ความเร็ว ตัวกรองและ Rules แทนคำ, อ่านเอกสาร, API, WAV และ OBS Subtitles
- YouTube LIVE (API และ Browser), TikTok LIVE (TikFinity และ Extension), Discord Bot/Client, อ่านชื่อผู้ส่งและอีโมจิ, Live queue และการป้องกันข้อความซ้ำ
- AI Processing/Translation (Ollama และ M2M100 แบบทดลอง), Prompt/Priority Instructions, เลือกภาษา, Keep Alive, Pre/Post-AI Rules และคิวเตรียมข้อความแบบไม่บล็อกเสียง
- AI Tool Calling แบบปิดเป็นค่าเริ่มต้น พร้อม Wikipedia/SearXNG/Ollama Web Search/Tavily, สิทธิ์อ่านไฟล์ที่อนุญาต, Windows DPAPI API Keys และโปรไฟล์ค้นหา JSON ไม่รวม Key

## ไฟล์ดาวน์โหลดที่แนบครบ (6 รายการ)

| Release Asset | รายละเอียด |
| --- | --- |
| VoxWeaveTTS-v0.7.1-portable.zip | Windows Portable หลัก: EXE + Python Runtime + MakHam ONNX + Web UI + AI + YouTube Browser fix + Extension source + เอกสาร |
| VoxWeaveTTS-TikTok-Extension-v0.2.5.zip | ส่วนเสริม TikTok LIVE Comments (ไฟล์เดิมที่ผ่านการตรวจ SHA) |
| VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel | โมเดลเสียง ThaiSom เสริม |
| VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel | โมเดลเสียง Vachana 4 เสียงเสริม |
| VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel | โมเดลแปลภาษา M2M100 Experimental (Runtime เสริมต้องเตรียมเอง) |
| SHA256SUMS-v0.7.1.txt | SHA-256 Checksums ของไฟล์ดาวน์โหลด 5 ชุดด้านบน |

โมเดลเสริมทั้งสามแจกแยกจาก Portable เพื่อไม่ให้ชุดหลักมีขนาดใหญ่; ไม่มี Ollama executable, PyTorch/Transformers Runtime สำหรับ M2M100, ไฟล์ Settings ส่วนตัวหรือ API Keys ใด ๆ รวมอยู่ใน Portable

## การติดตั้งและอัปเดต

1. ดาวน์โหลด Windows Portable v0.7.1 แล้วแตก ZIP ลงในโฟลเดอร์ที่เขียนได้ เรียกใช้งาน VoxWeaveTTS.exe หรือ Start-Console.cmd
2. ก่อนอัปเกรดให้ปิดโปรแกรมและสำรอง data/settings, data/filters, data/dictionaries, data/profiles และ models/packages เพื่อคงการตั้งค่าเดิมไว้
3. ใน YouTube LIVE (Browser) กรอก Video ID/URL แล้วกดเชื่อมต่อ โปรแกรมจะพยายามเลือก Live chat เองและแสดงสถานะที่ตรวจพบ
4. โมเดลเสียงเสริมติดตั้งผ่าน TTS Model Packages; M2M100 ใช้ตัวจัดการ AI Model Package/ขั้นตอนใน docs/M2M100_SETUP_TH.md และต้องมี Python dependencies เสริม
5. ตรวจสอบ SHA-256 ก่อนติดตั้งโมเดลเสริมจากผู้ให้บริการอื่น

## ผลตรวจสอบ / ขอบเขต

- มี Unit Tests สำหรับ Top → Live, การไม่อ่านข้อความเก่า/ซ้ำ, การจำกัดเวลารอเปลี่ยนโหมด, Chromium background flags และการส่งสถานะถึง UI
- มี Chrome CDP integration test ที่ใช้ Browser จริงกับหน้า DOM จำลองและตรวจว่าคำสั่ง Focus Emulation / Active Lifecycle สำเร็จ
- รัน Python/JavaScript Regression ครอบคลุมระบบเสียงเดิมและส่วนเสริมทั้งหมด
- ยังไม่ได้ตรวจ YouTube LIVE จริงแบบย่อหน้าต่างเป็นเวลานาน และการอ่าน DOM ของ YouTube ไม่ใช่ช่องทาง API อย่างเป็นทางการ สำหรับช่องทางทางการใช้ YouTube LIVE (API)
- M2M100 ยังคง Experimental: การทดสอบตัวอย่างก่อนหน้าพบคำแปลผิดความหมาย 2 จาก 3 กรณี ไม่ควรใช้กับ Live โดยไม่มีคนตรวจ

## คู่มือ

README_TH.md, docs/YOUTUBE_BROWSER_READER_TH.md, docs/AI_TOOL_CALLING_TH.md, docs/M2M100_SETUP_TH.md, CHANGELOG.md

**สิทธิ์ใช้งาน:** VoxWeaveTTS MIT; ตรวจ License/Attribution ของโมเดลและส่วนเสริมแต่ละชุดแยกกันก่อนนำไปใช้
