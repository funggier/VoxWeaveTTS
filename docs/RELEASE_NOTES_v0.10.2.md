# VoxWeaveTTS v0.10.2 — Portable Doctor, M2M100 CPU และการยืนยันก่อนติดตั้ง Runtime

**Windows 10/11 x64 · Python 3.11 Portable · 18 พฤศจิกายน 2026**

รุ่นนี้ปรับความพร้อมของระบบ TTS และการแปลภาษาที่มีอยู่แล้ว ไม่ใช่การเพิ่ม Voice Cloning หรือเปลี่ยนรูปแบบโมเดล .vwmodel v2 ผู้ใช้แตก ZIP และเปิด MakHam Paradee ได้ทันที ส่วนโมเดลและ Runtime ใหญ่เป็นตัวเลือกแยกติดตั้ง

## เปลี่ยนแปลงจาก v0.10.1

1. **Portable Doctor** — เพิ่ม scripts/Check-Portable.ps1 ตรวจ Python/uv ใน Portable, Native v2 Model, Runtime, ความผิดปกติหลังย้ายโฟลเดอร์ และ Wheelhouse; รองรับ JSON, Strict และการตรวจ SHA-256 แบบเลือกใช้ การตรวจปกติไม่ติดตั้งหรือโหลดโมเดล
2. **Offline Runtime & Relocation** — ใช้ uv.exe ที่บันเดิลในโปรแกรมเป็นหลัก, ตรวจ Interpreter/Dependencies หลัง Repair และ Rollback เมื่อไม่ผ่าน ทดสอบแยกโฟลเดอร์ ติดตั้ง PyThaiTTS/Sherpa/M2M100 ผ่าน Trusted Wheelhouse, ย้ายโฟลเดอร์ และ Repair แบบ Offline สำเร็จบน **Windows เครื่องพัฒนาเดียวกัน**
3. **M2M100 CPU** — จำกัด Worker PyTorch เป็น 2 intra-op threads และ 1 inter-op thread เพื่อลดปัญหา CPU Oversubscription เพิ่ม scripts/Verify-M2M100Runtime.ps1 ทดสอบแปลอังกฤษ↔ไทยจริง, ตรวจ Output เบื้องต้น และปิด Worker แบบสุภาพก่อน Force Stop ผลทดสอบข้อความสั้นสำเร็จ แต่ยังไม่ได้ประเมินคุณภาพคำแปลอย่างเป็นระบบ
4. **การแยกสิทธิ์จากสถานะ Runtime** — Runtime Registry / Portable Doctor แยกสถานะรันได้และ SHA-256 ตรงจากสิทธิ์ใช้งานเชิงพาณิชย์/การแจกจ่าย พร้อมคำเตือน Wayu NC และ Candidate Vachana/Kokoro
5. **ยอมรับเงื่อนไขก่อนติดตั้ง** — หน้า Engine Providers ต้องให้ผู้ใช้ติ๊กยืนยันสำหรับ Vachana, Kokoro และ Wayu NC โดย Wayu NC มี Checkbox แยกเพื่อรับทราบ NonCommercial; มีหน้าต่างยืนยันซ้ำ ตรวจคำขอฝั่ง Server/Installer และไม่บันทึกการยอมรับถาวร PowerShell CLI รองรับ -AcceptProviderTerms และ -AcknowledgeNonCommercial สำหรับกรณีที่ต้องใช้

## ไฟล์ Release

- **VoxWeaveTTS-v0.10.2-portable.zip** — โปรแกรม, MakHam Paradee, Web UI, Windows Launcher, Portable Doctor และเครื่องมือควบคุม Runtime พร้อมใช้ภายในโฟลเดอร์ ไม่ต้องติดตั้ง Python/uv ใน Windows
- **โมเดล Universal .vwmodel v2 แยก 8 รายการ** — MakHam, FastThaiG2P ThaiSom, Vachana Thai 4 Voices, Kokoro82M, MeloTTS Chinese, Supertonic 3, Wayu Paxa Edge NC และ M2M100 418M Translation; ไฟล์เสริมไม่ได้รวมทั้งหมดใน Portable หลัก
- **Verified Offline Wheelhouses 3 รายการ** — Sherpa, PyThaiTTS, M2M100 สำหรับ Windows x64 / Python 3.11 เป็นไฟล์ Dependencies ที่มี Trusted Lock / SHA-256 แยกจาก Model Weights
- **TikTok Extension ZIP, Documentation ZIP, Source ZIP และ SHA256SUMS** สำหรับตรวจดาวน์โหลด

**วิธีใช้งาน:** แตก Portable ZIP ลงในโฟลเดอร์ที่เขียนได้ เช่น T:\Apps\VoxWeaveTTS แล้วเปิด VoxWeaveTTS.exe หรือ Start-Console.cmd และเข้า http://127.0.0.1:8765 หากมีเวอร์ชันเก่า ให้สำรอง Settings/Presets/Models ก่อนเปลี่ยนรุ่น อย่าทับโฟลเดอร์เดิมโดยไม่มี Backup

**โมเดลเสริม:** ดาวน์โหลด .vwmodel v2 จาก Release แล้วใช้ Model Packages ติดตั้ง จากนั้นติดตั้ง Runtime ผ่าน Engine Providers/Runtime Registry หากเป็น Vachana/Kokoro/Wayu ต้องอ่านและยอมรับเงื่อนไขก่อนเริ่มติดตั้ง Dependencies บางตัวต้องใช้อินเทอร์เน็ต

## สิทธิ์ของโมเดลและ Third-party

- **Wayu Paxa Edge NC:** น้ำหนักโมเดล **CC BY-NC 4.0 / ห้ามใช้เชิงพาณิชย์** ผู้ติดตั้งรับทราบได้ แต่การกดยอมรับไม่ได้มอบสิทธิ์ใหม่
- **Vachana/Kokoro Runtime:** อนุญาตให้ผู้ใช้เลือกติดตั้ง Dependencies จาก Recipe ที่กำหนดไว้ใน Source โดยยอมรับคำเตือนเอง แต่ **ไม่ได้เผยแพร่ Candidate Wheelhouse** ของสองตัวนี้ เนื่องจากต้องตรวจ License และ Native Notices ของ Wheel ต่าง ๆ ให้ครบ (รวม phonemizer GPL)
- **Sherpa/PyThaiTTS/M2M100:** Wheelhouse ที่ล็อก SHA-256 เป็นการยืนยันความถูกต้องเชิงเทคนิค ไม่ใช่ Commercial Clearance; โมเดลและ Dependencies มี License แยกกัน
- ไม่มีเสียงส่วนตัวหรือ Credentials ของผู้ใช้ใน Release; ผู้ใช้ต้องศึกษาข้อกำหนดของ Model Weights, Voicepack, Dataset และ Runtime ที่เลือกใช้

## การตรวจสอบและข้อจำกัด

- Regression Tests และ UI Smoke Tests ในขั้นตอนเตรียม Release ผ่านตามบันทึกของชุดพัฒนา
- **ยังไม่ได้ทดสอบบน Windows คนละเครื่อง** ที่ไม่มีเครื่องมือพัฒนา แม้การแตกโฟลเดอร์/Relocation/Offline Repair ผ่านบนเครื่องพัฒนาแล้ว
- ยืนยันการกดยินยอมใน UI, HTTP API และ PowerShell รวมถึงคำขอที่ต้องถูกปฏิเสธแล้ว แต่ **ยังไม่ยืนยัน Fresh Online Download/Install ของ Vachana/Kokoro/Wayu ครบทั้งสามรายการบนเครื่องใหม่**
- M2M100 ใช้ RAM/Commit สูง และผลคำแปลสั้นที่ทดสอบไม่รับประกันความถูกต้องทุกภาษา
- YouTube/TikTok Live ที่ทำงานต่อเนื่องหลายชั่วโมงหรือเบื้องหลัง ยังต้องทดสอบกับ Stream ที่ได้รับอนุญาตจริง
- Voice Cloning/Training, Native Emotion หลายโมเดล, Streaming Hard Cancel และ Automatic Word/Syllable Forced Alignment ยังไม่เสร็จในรุ่นนี้

อ่านต่อ: [Portable Doctor](PORTABLE_DIAGNOSTICS_TH.md) · [M2M100 CPU](M2M100_CPU_RUNTIME_VALIDATION_TH.md) · [Provider Rights & Consent](PROVIDER_RIGHTS_READINESS_TH.md) · [Universal v2 Packages](UNIVERSAL_VWMODEL_V2_TH.md)

Release: https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.10.2
