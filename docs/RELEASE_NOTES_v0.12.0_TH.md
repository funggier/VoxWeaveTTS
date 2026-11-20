# VoxWeaveTTS v0.12.0 — Universal v4 Core-only Portable

**Release date:** 20 พฤศจิกายน 2026

**ประเภท Release:** Windows x64 Portable / Core-only / Universal `.vwmodel v4` เท่านั้น

## ข้อควรทราบก่อนดาวน์โหลด

**ZIP ตัวโปรแกรมนี้ไม่มีโมเดลสร้างเสียง TTS หรือโมเดลแปลภาษาติดมาด้วย** เพื่อไม่แจกจ่ายน้ำหนักโมเดลและ Dependencies ที่สิทธิ์ยังตรวจไม่ครบ ผู้ใช้ต้องหาและติดตั้งแพ็กเกจ `.vwmodel v4` ที่มีสิทธิ์ใช้งานด้วยตนเองก่อนจึงจะสร้างเสียงพูดหรือแปลผ่านโมเดลออฟไลน์ได้

ไฟล์ `VoxWeaveTTS-v0.12.0-v4-demo-tone.vwmodel` ที่แถมแยกเป็น Asset เป็น **ตัวอย่างเสียงโทน** สำหรับทดสอบระบบ Installer/Worker เท่านั้น ไม่ใช่โมเดลแปลงข้อความเป็นเสียงพูด และไม่สามารถใช้แทนโมเดล TTS จริงได้

## วิธีเริ่มต้นใช้งาน

1. ดาวน์โหลด `VoxWeaveTTS-v0.12.0-portable.zip` จาก Release นี้ แล้วแตก ZIP ไปยังโฟลเดอร์ใดก็ได้บน Windows 10/11 x64
2. เปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd` ภายในโฟลเดอร์ `VoxWeaveTTS`
3. เปิด `http://127.0.0.1:8765/` เมื่อโปรแกรมเริ่มทำงาน (ต้องไม่มีกระบวนการอื่นใช้พอร์ตนี้)
4. ไปที่ **ตั้งค่า → จัดการโมเดล** กดติดตั้งและเลือกไฟล์ `.vwmodel v4` ของผู้เผยแพร่ที่คุณเชื่อถือ และตรวจเงื่อนไข License ของแพ็กเกจนั้น
5. เมื่อโมเดลเสียงติดตั้งและแสดงสถานะพร้อมแล้ว จึงเลือก Engine/Model สำหรับการอ่านเอกสารหรือ Live Chat

การติดตั้งทำงานแบบออฟไลน์จาก **ไฟล์แพ็กเกจเดียว** รวม Worker/Assets/Dependencies ที่แพ็กเกจต้องการ ไม่ตรวจสอบกับ License Server และไม่ดาวน์โหลดสิ่งอื่นขณะติดตั้ง

**ทดลองระบบติดตั้งโดยไม่ใช้โมเดลบุคคลที่สาม:** เลือกดาวน์โหลดไฟล์ Demo Tone แยกต่างหาก ติดตั้งแบบเดียวกับโมเดลจริง แล้วทดลองสร้างเสียงโทน จากนั้นถอนติดตั้งได้ แพ็กเกจ Demo Tone เขียนขึ้นในโปรเจกต์ VoxWeaveTTS และใช้ MIT

## การเปลี่ยนแปลงหลัก

- **v4-only Core:** ลบการรองรับ v1/v2/v3 ออกจากโค้ดติดตั้งและรันโมเดล ไม่ใช้ตัว Adapter รุ่นเก่าของ Core
- **Future-proof Plugin:** TTS/Translation ใช้ Worker Protocol v1 ที่อยู่ภายใน `.vwmodel v4` ไม่จำเป็นต้องอัปเดต Core เพื่อรองรับสถาปัตยกรรมที่ปฏิบัติตาม Protocol
- **Runtime ออฟไลน์และแยกขาด:** ติดตั้งจาก Wheel/Native Runtime ของแต่ละแพ็กเกจ พร้อมแยกสภาพแวดล้อมและรองรับการย้ายทั้งโฟลเดอร์
- **Windows Portable ขนาดเล็กกว่าเดิม:** Python Core ใช้ Dependencies ที่จำเป็นสำหรับ API/ระบบ YouTube gRPC และตัวจัดการโมเดลเท่านั้น; ไม่มี PyTorch, ONNX Runtime, NumPy หรือเสียงโมเดล QA รวมมาด้วย
- **UI v4-only:** ติดตั้ง/ถอนแพ็กเกจและแสดงสถานะได้ โดยเตือนให้ผู้ใช้ติดตั้งโมเดลเมื่อยังไม่มี
- คงระบบอ่านเอกสาร, Live Chat (Discord, YouTube, TikTok), Translation/Ollama, Queue, Rules และ Subtitle/OBS Overlay ใน Core
- เอกสารสร้างแพ็กเกจในโฟลเดอร์ `examples/` มีตัวอย่าง **v4 เท่านั้น** ทั้ง Python, Wheel, Native Worker, TTS และ Translation
- รวมต้นฉบับ License ของ uv 0.12.9 และเอกสารสิทธิ์ของ Dependencies Core ในไฟล์ Portable

## สิทธิ์และข้อจำกัด

โมเดล QA ทั้ง 8 (MakHam, FastThaiG2P, Melo Chinese, Supertonic 3, Kokoro, Vachana, Wayu Paxa Edge NC และ M2M100) **ยังไม่เผยแพร่ใน Release นี้** แม้ว่าจะทดสอบเชิงเทคนิคผ่านครบ เพราะยังต้องตรวจสิทธิ์แจกจ่ายไฟล์โมเดล/Dependencies และข้อกำหนด Attribution

โดยเฉพาะ Wayu Paxa Edge NC ใช้เงื่อนไข NonCommercial, Supertonic 3 ใช้ OpenRAIL-M และบางตัวมี Library Copyleft หรือมี License ที่ไม่ชัดเจนใน Wheel ไม่มีการแก้ Manifest เพื่อปลดข้อจำกัดเหล่านี้

การเลือกติดตั้งแพ็กเกจถือเป็นการยอมรับความเสี่ยงจาก **Worker Code ที่ทำงานด้วยสิทธิ์ของผู้ใช้ Windows** และยอมรับเงื่อนไขที่แพ็กเกจประกาศไว้ ไม่ได้หมายความว่า VoxWeaveTTS รับรองผู้เผยแพร่หรือให้สิทธิ์แจกจ่ายต่อ

หลักฐานอ้างอิง License: [V4_RIGHTS_REVIEW_TH.md](V4_RIGHTS_REVIEW_TH.md) · [V4_UPSTREAM_LICENSE_EVIDENCE_TH.md](V4_UPSTREAM_LICENSE_EVIDENCE_TH.md)

## การตรวจสอบ Release

- ตัวโปรแกรมและ Assets ทั้งหมดมี SHA-256 ในไฟล์ `SHA256SUMS-v0.12.0.txt`
- ทดสอบเปิด API ผ่านพอร์ต Loopback ชั่วคราว, YouTube gRPC, ติดตั้งแพ็กเกจ Demo Tone ออฟไลน์, ได้ไฟล์ WAV จริง, ถอนติดตั้งสำเร็จ
- ตรวจ ZIP CRC, แตก ZIP ไปโฟลเดอร์ใหม่, ไม่มีโมเดล QA, ไม่มีข้อมูลส่วนตัว/Logs, และไม่มี v3
- ชุด Regression Tests ต้องผ่านบน Python 3.11, Python 3.13 และ JavaScript ใน GitHub Actions ก่อนเผยแพร่

**หมายเหตุ:** รุ่น v0.11.0 เป็น Release เก่าที่ใช้ v3 ไม่สามารถนำแพ็กเกจ v3 มาใช้กับ v0.12.0 ได้ ต้องใช้ `.vwmodel v4` เท่านั้น
