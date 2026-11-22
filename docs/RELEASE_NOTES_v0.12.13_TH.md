# VoxWeaveTTS v0.12.13 — Core-first Live Control & Reliable Stop

เผยแพร่: 23 พฤศจิกายน 2026 · Windows x64 Portable / Relocatable · รองรับแพ็กเกจโมเดล `.vwmodel` **V4 เท่านั้น**

## ดาวน์โหลด

- **`VoxWeaveTTS-v0.12.13-portable.zip`** — **โปรแกรมหลัก Server/Core** พร้อม Launcher, Web Control, ตัวรับแชท, คิวแปล/TTS, ระบบเล่นเสียง และ Model Package Manager แบบ Portable
- **`VoxWeaveTTS-Client-v0.12.13-portable.zip`** — โปรแกรม Remote Desktop Client **ตัวเลือกเสริม** ใช้ความสามารถเดิมโดย **ไม่ได้เพิ่มฟีเจอร์ Client ในรุ่นนี้** ไม่มี Core หรือโมเดลเสียง
- **`SHA256SUMS-v0.12.13.txt`** — ตรวจสอบ SHA-256 ของทั้งสอง ZIP

รุ่นนี้ **ไม่รวมโมเดลเสียงหรือไฟล์น้ำหนักโมเดล**; ดาวน์โหลด V4 Model Packs แยกด้านล่างและติดตั้งแบบออฟไลน์ผ่านหน้า Model Packages

## จุดเปลี่ยนสำคัญ

### 1. Core เป็นเจ้าของการทำงานจริง

- การติดตั้งใหม่เลือก **ทำงานบนคอมพิวเตอร์ (Core)** เป็นค่าเริ่มต้น ข้อความ Live ที่ Core รองรับจึงเข้าสู่ระบบรับแชท → คิว → แปลภาษา/จัดข้อความ → TTS → เล่นเสียงที่ Server โดยไม่ต้องเปิด Browser ค้างไว้
- คงโหมด **Browser** เดิมไว้เป็นทางเลือกที่ผู้ใช้เลือกเอง โดยยังรักษาค่าที่ตั้งไว้เดิมหากเคยกำหนดเป็น Browser
- หน้า Browser เป็นแผงควบคุมและแสดงผลสถานะที่ **อ่านจาก Core จริง** ทั้งสถานะการรับข้อความ คิวกำลังแปล/สร้างเสียง เสียงพร้อมเล่น ประวัติการอ่าน และค่าตั้งเสียง
- เปิดหน้าเว็บใหม่หรือรีเฟรชแล้ว **ไม่สั่งเปิด Studio, เริ่มแปล, เริ่ม TTS, เริ่ม Source หรือยึดสิทธิ์แท็บเอง** แม้การติดต่อ Core จะล้มเหลว หน้าเว็บไม่ควรเปลี่ยนการทำงาน Server โดยไม่มีคำสั่งผู้ใช้
- ไม่เพิ่ม Timer/EventSource ซ้ำสำหรับ Core Dashboard; ดึงรายละเอียดเฉพาะเมื่อ cursor สถานะเปลี่ยนและจำกัดการร้องขอเมื่อ Server ตอบผิดพลาด

### 2. คำสั่งหยุดจริงและสอดคล้องกับ Core

- **หยุดเสียงและพักคิว Core** หยุดการเล่นปัจจุบัน พักการรับงานเสียงใหม่ไว้รอการกด **อ่านอัตโนมัติต่อ** อย่างชัดเจน
- **หยุดรับข้อความเฉพาะโหมด** ปิด Source ของโหมดนั้น ล้างคิวต้นทางและข้อความ Core ที่ยังค้าง ยกเลิกงานที่ยังไม่จบ และหยุดเสียงของโหมดนั้น โดยไม่กระทบงานของโหมดอื่น
- กรณีกด Stop ระหว่างส่งงานเข้า TTS แล้ว HTTP ตอบช้า Core จะยกเลิกงานที่ตอบกลับมาภายหลัง ไม่ปล่อยเสียงใหม่หลุดออกจากคิว; สำหรับ **พักคิว** จะเก็บข้อความที่ยังไม่ถูกรับเข้า TTS เพื่ออ่านต่อเมื่อผู้ใช้สั่ง Resume
- ถ้าตัวส่งเสียงตอบว่าเล่นสำเร็จหลังสั่งหยุด Core จะไม่บันทึกเสียงนั้นเป็น **อ่านจบ**
- สามารถกดหยุดจากหน้า Browser ที่เพิ่งรีเฟรชได้ โดยไม่ต้องพึ่งโทเคนที่อยู่ในแท็บเก่า
- งานแปลหรือโมเดลที่กำลังประมวลผลอยู่จริงอาจต้องใช้เวลาคืนทรัพยากร; การยกเลิกป้องกันการส่งผลลัพธ์นั้นไปเล่น **ไม่ใช่การรับประกันว่าจะหยุด CPU/GPU ทันที**

### 3. TikFinity WebSocket อยู่ภายใน Core

- ในโหมด Computer ระบบเชื่อมต่อกับ **TikFinity Desktop ที่ `ws://127.0.0.1:21213/`** จาก Core โดยตรง ไม่จำเป็นต้องให้ Browser ควบคุมเชื่อม WebSocket ค้างไว้
- หาก Socket ปิดหรือการเชื่อมต่อหลุดชั่วคราว Core สามารถลองเชื่อมต่อใหม่ตามจังหวะ Retry ที่จำกัด โดยไม่ต้องรีเฟรช Browser
- **ผู้ใช้กดหยุด** จะปิดการเชื่อมต่อและไม่ให้ Source กลับมาเริ่มเองจนกดเชื่อมต่อใหม่
- จำกัด URL ของ TikFinity ที่ Core ให้ใช้เฉพาะ localhost ดังกล่าว; ไม่มีการเพิ่มแพ็กเกจ Python WebSocket ภายนอก

### 4. สถานะบน Browser ตรงกับการทำงานจริง

- แสดงโหมดและเวอร์ชันที่ Server รายงานจริง พร้อมสถานะพักคิว ตัวนับงาน และรายละเอียดการสร้างเสียง/ข้อความส่งเข้าโมเดลที่ทราบจาก Core
- ประวัติแชท/การเล่นเสียงใน Core ยังคงแสดงได้หลังรีเฟรช Browser แต่เก็บใน RAM และมีจำนวนจำกัด; **ไม่อยู่ข้ามการรีสตาร์ต Server**
- ไม่เอาข้อความแชทดิบมาปลอมเป็นข้อความที่แปลสำเร็จ; เมื่อยังไม่มีข้อมูลจากโมเดลจะแสดงสถานะรอ/ไม่พร้อมตามจริง
- เอาการกด **ทดลองประมวลผลข้อความอัตโนมัติเมื่อเปิดหน้าเว็บ** ออกแล้ว ต้องกดทดลองเองเท่านั้น

## การใช้ LAN และข้อควรระวัง

- เปิด Web Control ผ่าน IP/Port ของ Launcher เช่น `http://192.168.1.165:8775/` (ตัวอย่าง ไม่ใช่พอร์ตตายตัว) ไม่จำเป็นต้องเปิด Remote Desktop Client API เพื่อควบคุมจาก Browser
- ระบบ Web Control, Live Audio Listener และ Remote Desktop Client API มีการตั้งค่าคนละส่วน อ่าน [คู่มือ LAN](https://github.com/funggier/VoxWeaveTTS/blob/v0.12.13/docs/LAN_CONNECTIONS_TH.md) และ [สถานะ Core บน Browser](https://github.com/funggier/VoxWeaveTTS/blob/v0.12.13/docs/COMPUTER_BROWSER_STATUS_TH.md)
- ควรใช้ HTTP ใน LAN/VPN ที่ไว้ใจได้เท่านั้น **อย่าเปิด Forward Port สู่ Internet โดยตรง**; Browser/Extension ที่เป็นผู้จับข้อมูล DOM อาจต้องคงหน้าเว็บไซต์ต้นทางไว้
- **อย่าแตก ZIP ทับโปรแกรมที่กำลังทำงาน** ให้ติดตั้งลงโฟลเดอร์ใหม่ก่อน ย้ายเฉพาะไฟล์ตั้งค่าและโมเดลที่ต้องการอย่างระมัดระวัง แล้วปิด Server รุ่นเดิมก่อนเริ่มรุ่นใหม่ เพื่อป้องกันพอร์ตชนกัน
- การสร้างเสียงขึ้นกับแพ็กเกจโมเดลที่ติดตั้งอย่างถูกต้อง; รุ่นนี้ทดสอบชุดโค้ด, HTTP, ไฟล์เสียงจำลอง และ Portable แต่ยังไม่ยืนยันการทำงานจริงของทุกแพลตฟอร์ม Live / ทุกโมเดล / ทุกอุปกรณ์กับผู้ใช้ปลายทาง

## ดาวน์โหลดแพ็กเกจโมเดล V4 (ติดตั้งแยก)

**[VoxWeaveTTS Model Packs V4 ทั้ง 7 แพ็กเกจ](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4)**

- [MakHam Paradee — Thai TTS](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-makham-paradee-1.0.0-format-v4.vwmodel)
- [FastThaiG2P Thai Som — Thai TTS](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-fastthaig2p-thai-som-0.3.0-format-v4.vwmodel)
- [Melo Chinese ONNX](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-melo-chinese-onnx-1.0.0-format-v4.vwmodel)
- [Supertonic 3 Multilingual INT8](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-supertonic3-multilingual-int8-1.0.0-format-v4.vwmodel)
- [Kokoro Multilingual INT8](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-kokoro-multilingual-int8-1.0.0-format-v4.vwmodel)
- [Wayu Paxa Edge NC](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-wayu-paxa-edge-nc-1.0.0-format-v4.vwmodel) — **CC BY-NC 4.0: ไม่อนุญาตใช้งานเชิงพาณิชย์**
- [M2M100 418M — โมเดลแปลภาษา ไม่ใช่ TTS](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-m2m100-418m-1.0.0-format-v4.vwmodel)

[SHA256SUMS ของโมเดล V4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/SHA256SUMS-v0.12.1-modelpacks-v4.txt) · [ตรวจสอบสิทธิ์และที่มาโมเดล](https://github.com/funggier/VoxWeaveTTS/blob/v0.12.13/docs/V4_RIGHTS_REVIEW_TH.md)

## การทดสอบก่อนเผยแพร่

- Python `unittest`: **487 tests ผ่าน (ข้าม 1)**
- Python `pytest` เฉพาะ Core/Stop/HTTP/TikFinity/LAN: **26 tests ผ่าน**
- JavaScript Browser Smoke: **44 ชุดผ่าน**
- GitHub Actions ล่าสุดบน Branch ก่อนปรับเลขเวอร์ชัน: Python 3.11, Python 3.13 และ JavaScript ผ่านทั้งหมด [ดู CI](https://github.com/funggier/VoxWeaveTTS/actions/runs/45050695536)
- Windows Portable Stage/embedded Python และ v4-only model-free packaging ตรวจสอบผ่าน; Release ชุดนี้ให้ดาวน์โหลดพร้อม SHA-256 เพื่อใช้ตรวจไฟล์
