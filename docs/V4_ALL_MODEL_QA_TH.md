# Universal v4 — บันทึกการย้ายโมเดลครบ 8 ตัว

สถานะ: 20 พฤศจิกายน 2026 — **ย้ายครบและทดสอบการทำงานจริงใน Portable QA สำเร็จ แต่ยังไม่อนุมัติให้เผยแพร่แพ็กเกจทั้งหมดสู่สาธารณะ**

## รูปแบบใหม่

โมเดล TTS ทุกตัวใช้ plugin/worker.py ที่แนบมากับแพ็กเกจ (ตัวอย่างต้นฉบับใน examples/v4-model-plugin) และติดตั้ง Dependencies จาก runtime/wheels ภายในไฟล์ .vwmodel v4 เดียว โดยไม่เพิ่มรายชื่อ Adapter ลงใน VoxWeaveTTS Core

โมเดลแปลภาษา M2M100 ใช้ plugin/worker.py ภายในแพ็กเกจของตนเอง ผ่าน Translation Worker Protocol v1 และ Runtime ที่แยกจาก TTS ตัวอื่น

## ผลการทดสอบจริง

| แพ็กเกจ v4 | Runtime | ผลการทดสอบบน Windows Portable QA | สถานะสิทธิ์ |
| --- | --- | --- | --- |
| MakHam Paradee | Python 3.11 + 26 Wheel (ครบในแพ็กเกจ v4) | ติดตั้งออฟไลน์, WAV ไทย 24,000 Hz, ถอนติดตั้ง ผ่าน | review_required |
| FastThaiG2P Thai Som | Python 3.11 + 26 Wheel | ติดตั้งออฟไลน์, WAV ไทย 24,000 Hz, ถอนติดตั้ง ผ่าน | review_required |
| Melo Chinese ONNX | Python 3.11 + 3 Wheel | ติดตั้งออฟไลน์, WAV จีน 44,100 Hz, ถอนติดตั้ง ผ่าน | review_required |
| Supertonic 3 Multilingual | Python 3.11 + 3 Wheel | ติดตั้งออฟไลน์, WAV อังกฤษ 44,100 Hz, ถอนติดตั้ง ผ่าน | review_required / OpenRAIL-M |
| Kokoro 82M Multilingual INT8 | Python 3.11 + 31 Wheel | ติดตั้งออฟไลน์, WAV อังกฤษและญี่ปุ่น 24,000 Hz, ถอนติดตั้ง ผ่าน | hold (GPL/Native Notices) |
| Vachana Thai 4 Voices | Python 3.11 + 14 Wheel | ติดตั้งออฟไลน์, WAV ไทย 22,050 Hz, ถอนติดตั้ง ผ่าน | hold (vachanatts Wheel) |
| Wayu Paxa Edge NC 12 Voices | Python 3.11 + 106 Wheel | ติดตั้งออฟไลน์, WAV ไทย 24,000 Hz, ถอนติดตั้ง ผ่าน | hold / CC BY-NC 4.0 |
| M2M100 418M Translation | Python 3.11 + 25 Wheel | ติดตั้งออฟไลน์, แปลอังกฤษ→ไทย และไทย→อังกฤษจริง, ถอนติดตั้ง ผ่าน | review_required |

**ข้อจำกัดที่ยังต้องทดสอบเพิ่ม:** เสียงทุกตัวในโมเดลหลายเสียง, การย้ายโฟลเดอร์ของทุกโมเดล, และคุณภาพภาษาที่แปลจาก M2M100 (Good morning. → สวัสดีเช้า ยังไม่เป็นธรรมชาติ)

## ตำแหน่งไฟล์ในเครื่องโปรเจกต์

- dist/ModelPackagesV4-QA/ — แพ็กเกจ v4 ทั้ง 8 ตัว (ไฟล์ UNRELEASED-QA)
- dist/ModelPackagesV4-QA/CATALOG-v4-QA.json — Catalog สำหรับ QA, Hash, สิทธิ์, จำนวนเสียง/Dependencies
- examples/ — มีเฉพาะตัวอย่าง v4 5 ประเภทสำหรับผู้สร้างแพ็กเกจในอนาคต
- scripts/build_vwmodel_v4.py — สร้างแพ็กเกจใหม่จาก Source + Manifest Spec; scripts/qa_add_v4_voice_language_maps.py — QA Metadata เสียง/ภาษาโดยตรวจ SHA-256 ทุก Asset
- scripts/verify_v4_model_inventory.py — ตรวจว่าครบ 8 ตัวและตรวจชุด Model Catalog; --deep ตรวจ SHA ทุกไฟล์ซ้ำ
- scripts/verify_all_v4_model_packages.py — ทดสอบแพ็กเกจ v4 ติดตั้ง→ใช้งานจริง→ถอน บน QA Portable โดยระบุ Stage เอง

## ตัวอย่างคำสั่ง

~~~powershell
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_model_inventory.py --write-catalog

# ทดสอบ SHA-256 ของทุกไฟล์ในทั้งแปดแพ็กเกจ (อ่านอย่างเดียว)
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_model_inventory.py --deep

# ตรวจการติดตั้งโมเดลจริงใน QA Stage ที่แยกออกจากตัวกำลังใช้งาน
.\dist\VoxWeaveTTS-v4-validation-20261120\runtime\python\python.exe -X utf8 scripts\verify_all_v4_model_packages.py --stage dist\VoxWeaveTTS-v4-validation-20261120 --models makham-paradee
~~~

## ขอบเขตและสิทธิ์

การแปลงเป็น v4 หรือการคลิกติดตั้งของผู้ใช้ไม่ได้เป็นหลักฐานว่าน้ำหนักโมเดลหรือ Wheel สามารถนำไปแจกจ่ายสาธารณะได้ แพ็กเกจทั้ง 8 ที่สร้างในรอบนี้จึงเป็น **QA ภายในเท่านั้น** ไม่ใช่ Official Release Assets ที่อนุมัติการใช้เชิงพาณิชย์

Wayu NC ยังจำกัดการใช้ตาม CC BY-NC 4.0 และต้องปฏิบัติตามข้อกำหนด NonCommercial; Kokoro และ Vachana ยังมีเอกสารสิทธิ์ Dependencies ที่ต้องสะสาง

GitHub Releases เก่ายังคงเปิดให้ดูเป็นประวัติ แต่โปรแกรม Core/Portable รุ่นใหม่เป็น v4-only และจะไม่เปิดแพ็กเกจรุ่นเก่า; อย่าเผยแพร่ QA Assets ที่สิทธิ์ยังไม่ผ่าน

VoxWeaveTTS v4 Core รองรับการติดตั้งโดยผู้ใช้เลือกไฟล์ครั้งเดียว และโปรแกรมตรวจ Hash/ZIP/Wheel ก่อนสร้าง Process ของ Plugin ตัวติดตั้งไม่ติดต่ออินเทอร์เน็ต โค้ด Plugin ถูกเลือกเชื่อถือโดยผู้ใช้และทำงานด้วยสิทธิ์ของผู้ใช้ Windows ไม่ได้เป็น Sandbox ที่รับประกันความปลอดภัย
