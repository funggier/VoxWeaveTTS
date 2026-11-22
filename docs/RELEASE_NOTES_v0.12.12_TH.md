# VoxWeaveTTS v0.12.12 — WASAPI/USB DAC Audio Fix, Live Queue Backpressure, Browser LAN Control

เผยแพร่: 22 พฤศจิกายน 2026 · Windows x64 Portable / Relocatable · Universal `.vwmodel` **v4 เท่านั้น**

## ดาวน์โหลดโปรแกรม

- **`VoxWeaveTTS-v0.12.12-portable.zip`** — Server/Core, เว็บควบคุม, Desktop UI ภายใน Server, เอนจิน, Model Package Manager, การแปลและ Live chat
- **`VoxWeaveTTS-Client-v0.12.12-portable.zip`** — โปรแกรม Remote Desktop Client แยก (คงฟังก์ชันจาก v0.12.11 โดยไม่ได้พัฒนาต่อ; ไม่มี Core, TTS Engine หรือโมเดล)
- **`SHA256SUMS-v0.12.12.txt`** — เช็ก SHA-256 ของ ZIP ทั้งสองไฟล์

**แตกไฟล์ ZIP ลงในโฟลเดอร์ใหม่** แล้วเปิด `VoxWeaveTTS.exe` ของ Server เป็นหลัก การออก Release นี้ **ไม่หยุดหรือเปลี่ยนไฟล์ของ Server ที่กำลังรันพอร์ต 8775 อัตโนมัติ** ให้หยุด Server รุ่นเก่าอย่างถูกวิธีและย้ายข้อมูลตั้งค่า/โมเดลที่ต้องการก่อนสลับไปใช้รุ่นใหม่

## สิ่งที่แก้ไข

### 1. เสียงไม่ออกบน USB DAC / Realtek WASAPI

ปัญหาต้นทาง: TTS WAV บางตัวสร้างเสียงที่ 22,050/24,000 Hz แต่การ์ดเสียง Windows บางตัวเปิด WASAPI ที่อัตรานั้นไม่ได้ ตัวอย่างอุปกรณ์ทดสอบ Headphones (Realtek USB2.0 Audio) ใช้ native 192,000 Hz

- **Auto Sample Rate** ลองต้นทางแล้ว fallback ไปใช้อัตราที่อุปกรณ์รับได้ พร้อมแปลง PCM16 ก่อนเล่นเสียงโดยไม่แก้ WAV ต้นฉบับ
- **Browser → ตั้งค่า → รูปแบบเสียง** สามารถเลือก Sample Rate Auto หรือค่าที่กำหนด, Mono/Stereo และ Buffer 20/50/100/200 ms
- แสดง Sample Rate ที่ส่งออกจริงและข้อผิดพลาดที่มีรายละเอียดมากขึ้นแทนข้อความกว้าง ๆ ว่าเสียงไม่พร้อม
- ตัวเลือกนี้ใช้กับการส่งเสียงออกลำโพง/USB DAC ของคอม ไม่ได้เปลี่ยนรูปแบบเสียงสตรีม Live Listener

**หลักฐาน:** ทดสอบสัญญาณเงียบ 24,000 Hz จริงผ่าน Realtek USB โดยอัปแซมเปิลเป็น 192,000 Hz สำเร็จ; มี unit test จำลองอุปกรณ์ที่ปฏิเสธ Sample Rate ที่ไม่รองรับ ยังไม่ใช่หลักฐานยืนยันว่าทุกโมเดล/ทุกประโยคใช้งานได้บนเครื่องจริงทุกเครื่อง

### 2. คิว TTS/แปลภาษาสะสมจนระบบทำงานช้า

- ลดการรับงานสร้างเสียงของ Computer Runtime ให้สอดคล้องกับโควตาการเตรียมเสียง/เสียงพร้อมเล่นที่ตั้งไว้ใน Live queue (ไม่ปล่อยให้ส่งงานใหม่ไหลไปเต็มเพดาน 768 งานของทะเบียนงาน)
- ทำ backpressure ที่ขอบเขต Source Manager; งานใหม่รออยู่ในคิวข้อความแชท โดย **ไม่สุ่มลบเอง** หากผู้ใช้ไม่ได้เปิดโหมดสุ่มลบ
- รักษาลำดับ FIFO ของงาน TTS และไม่เริ่มสร้าง WAV จากทุกงานที่อยู่สถานะ prepared พร้อมกัน
- ปรับจังหวะรวมข้อความสั้นเป็นชุดก่อนเรียก Ollama เมื่อเปิด Batch Translation เพื่อลดการเรียกที่แยกย่อยเกินจำเป็น
- แสดงจำนวนงานเตรียม/แปล, สร้างเสียง, พร้อมเล่น และข้อผิดพลาดผ่าน Browser Settings

**ข้อจำกัด:** การแปลด้วย LLM อาจยังใช้เวลามากตามความเร็วรุ่นโมเดลและประโยค; backpressure ไม่ทำให้โมเดลเร็วขึ้นหรือรับประกันว่าเครือข่ายต้นทางจะเก็บแชทไว้ตลอดไป การเปลี่ยน Core ขณะมีคิวค้างอยู่จะไม่รักษางานใน RAM หลังรีสตาร์ต

### 3. แยกการเชื่อมต่อ Server / Browser / Remote Client ผ่าน LAN

| ช่องทาง | หน้าที่ | พอร์ตตัวอย่าง | ตั้งค่าจาก |
|---|---|---|---|
| **Web Control** | ควบคุม Server ผ่าน Firefox/Browser จากคอม/โทรศัพท์ | **8775** | **Server Launcher `VoxWeaveTTS.exe`** → Network |
| **Live Audio Listener** | ฟังเสียงที่ Server ถ่ายทอดออกมา | **8766** | แท็บ **ตั้งค่า** → Live Audio Listener |
| **Remote Desktop Client API** (ยังไม่เน้นพัฒนา) | ใช้กับโปรแกรม Client Portable แยก | **8776** | แท็บ **ตั้งค่า** → Remote Desktop Client API (ขั้นสูง) |

การควบคุมผ่าน **Browser ไม่จำเป็นต้องเปิด Remote Desktop Client API** หน้าเว็บแสดง IP/Port/Username **ที่ Server กำลังใช้อยู่**, แนะนำ URL ที่เข้าถึงได้, มีปุ่มคัดลอก URL และบอกว่าต้องไปเปลี่ยนค่า Web Control ใน Launcher

**สำคัญ:** IP `0.0.0.0` เป็นค่าที่ Server ใช้เปิดรับ ไม่ใช่ IP สำหรับ Browser อีกเครื่อง ให้เปิด `http://192.168.1.165:8775/` ตาม IP/Port จริงของ Server (ค่าในตัวอย่างไม่ใช่พอร์ตบังคับ) บัญชี Web Control อยู่ใน `data/network.json` ส่วน Remote Desktop Client API ใช้ไฟล์ `data/settings/network.json` และบัญชีแยกกัน

อ่าน **[คู่มือ LAN ของทั้งสามระบบ](https://github.com/funggier/VoxWeaveTTS/blob/v0.12.12/docs/LAN_CONNECTIONS_TH.md)** และ [การตั้งค่า IP/Port](https://github.com/funggier/VoxWeaveTTS/blob/v0.12.12/docs/NETWORK_TH.md)

## ดาวน์โหลดโมเดล V4 แยก

Server ZIP ไม่บันเดิลน้ำหนักโมเดล; ติดตั้งโมเดลด้วยไฟล์ `.vwmodel` V4 แบบออฟไลน์ผ่านหน้า Model Packages

**[ดาวน์โหลด Model Packs V4 ทั้ง 7 ตัว](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4)**

- [MakHam Paradee — TTS ไทย](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-makham-paradee-1.0.0-format-v4.vwmodel)
- [FastThaiG2P Thai Som — TTS ไทย](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-fastthaig2p-thai-som-0.3.0-format-v4.vwmodel)
- [Melo Chinese ONNX](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-melo-chinese-onnx-1.0.0-format-v4.vwmodel)
- [Supertonic 3 Multilingual INT8](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-supertonic3-multilingual-int8-1.0.0-format-v4.vwmodel)
- [Kokoro Multilingual INT8](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-kokoro-multilingual-int8-1.0.0-format-v4.vwmodel)
- [Wayu Paxa Edge NC](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-wayu-paxa-edge-nc-1.0.0-format-v4.vwmodel) — **CC BY-NC 4.0: ไม่อนุญาตใช้เชิงพาณิชย์**
- [M2M100 418M — โมเดลแปลภาษา (ไม่ใช่ TTS)](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-m2m100-418m-1.0.0-format-v4.vwmodel)

ตรวจไฟล์ด้วย [SHA256SUMS ของ Model Packs V4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/SHA256SUMS-v0.12.1-modelpacks-v4.txt) และอ่านเอกสารสิทธิ์ภายในแต่ละแพ็กเกจ

## ความปลอดภัยและขอบเขต

- Web Control / Remote API เป็น HTTP สำหรับ LAN/VPN ที่เชื่อถือได้ ไม่ควร Forward Port ออก Internet โดยตรง; แนะนำรหัสผ่านยาวกว่าขั้นต่ำ 4 ตัวอักษร
- Live Audio Listener ส่ง PCM สดโดยใช้โทเคนรับฟัง ส่วน Browser Control ใช้บัญชีใน Launcher และ Remote Desktop Client API มีบัญชีของตนเอง
- ไม่มีการเปลี่ยนฟังก์ชันโปรแกรม Remote Desktop Client หรือแจกน้ำหนักโมเดลเพิ่มใน Release นี้
- หน้าเว็บจากเครื่องอื่นที่ต้องเปลี่ยน IP/Port ฝั่ง Server ต้องทำที่ Launcher บนเครื่อง Server เอง แล้ว Restart Core
- Browser/Extension ของบางแพลตฟอร์มยังต้องเปิดหน้าต้นทางไว้ตามกลไกของแหล่งแชท
