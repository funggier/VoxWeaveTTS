# สถานะสิทธิ์และการเผยแพร่ Dependencies ของ TTS Providers (18 พฤศจิกายน 2026)

**สถานะ: งานพัฒนาหลัง v0.10.1 ยังไม่ใช่ Release ใหม่**

เอกสารนี้ใช้กับ `Runtime Registry`, `Portable Doctor` และขั้นตอนคัดเลือก `Verified Offline Wheelhouse` ของ VoxWeaveTTS โดยแยกความหมายของ
**รันได้ (operational readiness)**, **ตรง SHA-256 (binary integrity)**, **ใช้เชิงพาณิชย์ได้ตามเงื่อนไข (commercial use)** และ **แจกไฟล์ Runtime ได้โดยปฏิบัติตาม License (redistribution compliance)** ออกจากกัน

Hash ตรง **ไม่ได้พิสูจน์สิทธิ์** และการมี Model Card ระบุ MIT/Apache ไม่ได้แปลว่า Dependencies, องค์ประกอบ Native หรือเสียงทุกชุดได้รับสิทธิ์แบบเดียวกัน

## ตารางติดตาม (ผลตรวจจาก Candidate Windows x64 / Python 3.11)

| Runtime | สภาพทางเทคนิค | สภาพสิทธิ์สำหรับการคัดเป็น Wheelhouse ใหม่ | สิ่งที่ยังติดขัด |
|---|---|---|---|
| **Wayu NC** | มี Native v2 แยก, Worker สังเคราะห์เสียงจริงได้, Recipe ยังใช้ Git/Direct URL | **HOLD — NonCommercial-only ของน้ำหนักโมเดล** | Model weights **CC BY-NC 4.0** ถึงแม้ Inference Code จะระบุ Apache-2.0; ไม่มี Verified Offline Lock/การตรวจ Dependency Closure และ Notice ทั้งหมด |
| **Vachana** | Candidate 14 Wheels, 58,375,295 bytes, ยังไม่เผยแพร่ Trusted Lock | **HOLD — Review Required** | `vachanatts 0.0.7` Wheel ไม่มี License Declaration และไม่มี License Text ใน Archive ที่ตรวจ แม้ Model Card จะกล่าวถึง MIT; ต้องยืนยันสิทธิ์ของแพ็กเกจโค้ดและเสียงแยกกัน |
| **Kokoro** | Candidate 31 Wheels, 92,429,433 bytes, ยังไม่เผยแพร่ Trusted Lock | **HOLD — Review Required** | `kokoro-onnx 0.6.0` กำหนด `phonemizer>=3.4.0` โดยตรง; Candidate มี `phonemizer 3.6.0` ซึ่งเป็น **GPLv3-or-later**; `espeakng-loader 0.2.4` Wheel ยังขาดเอกสาร License ภายใน Archive ที่ตรวจ ต้องประเมินสิทธิ์ Native eSpeak/UniDic/OpenJTalk และ Notices |
| Sherpa, PyThaiTTS, M2M100 | มี Lock/Wheelhouse ที่เผยแพร่ก่อนหน้านี้ | **Review Required** (ไม่ถือเป็น Commercial-Cleared) | ต้องตรวจความครบถ้วนของ Third-party Notices/Runtime Binary ที่แจกจริง ไม่ถอน Release เดิมอัตโนมัติ |

**ความหมายที่ถูกต้อง:** GPLv3 อนุญาตการใช้งานเชิงพาณิชย์ แต่การแจกจ่ายหรือรวมซอฟต์แวร์ที่มี GPL ต้องประเมินข้อผูกพันของ Copyleft, Source และ Notices ให้สอดคล้องกับรูปแบบการแจกจ่ายของโปรเจกต์ ดังนั้น **ไม่ได้บอกว่า Kokoro ห้ามใช้เชิงพาณิชย์ทั้งหมด** แต่ไม่ควรประกาศว่า Cleared ก่อนตรวจเสร็จ

## สิ่งที่เพิ่มใน Source

- `provider_rights.py` เป็น **First-party, Read-only Policy**: ระบุสถานะ `hold` สำหรับทั้งสาม Runtime โดยข้อมูล Model Package ที่นำเข้าจากภายนอกไม่สามารถเปลี่ยนสถานะนี้ได้
- `runtime_registry.inventory()` ส่งคืน `rights_review` แยกจาก `ready`, `health_state` และ `wheelhouse`; หน้า Runtime Registry แสดง `Rights: HOLD` หรือ `Review required` ผ่าน `textContent` ไม่ใส่ HTML จาก Metadata ภายนอก
- Portable Doctor รวม `rights_review` ในผล JSON/ข้อความและจำนวนรายการ HOLD แต่สถานะ `overall_state=ready` ยังคงเป็น **ความพร้อมเชิงเทคนิคเท่านั้น** ไม่ใช่สิทธิ์
- `prepare_verified_wheelhouse.py --publish-reviewed` **ถูกปฏิเสธ** สำหรับ Wayu NC / Vachana / Kokoro ตราบที่ Policy ยังเป็น HOLD แม้ผู้เรียกจะระบุ Flag ว่า Reviewed เพื่อป้องกันการสร้าง First-party Trusted Lock โดยไม่ตั้งใจ; ยังคงสร้าง Draft เพื่อการตรวจสอบได้
- `audit_wheelhouse_rights.py` บันทึก SHA-256 ของ Wheel ทุกตัว, SHA-256 ของ Recipe, Python ABI, Platform, สถานะ Review ที่เป็น App-owned และรายการ License Flags ลง `cache/wheelhouse-rights/<id>.json` (ไม่ได้เผยแพร่ไฟล์ Cache และ **ไม่ได้ให้ Legal Clearance**)
- ไม่ได้เปลี่ยนความสามารถในการใช้ Runtime ส่วนตัวที่ติดตั้งไว้ก่อน หรือไล่ลบไฟล์โมเดล/Runtime ของผู้ใช้ ข้อบังคับใหม่นี้อยู่เฉพาะขั้นตอน **เตรียม Wheelhouse สำหรับการเผยแพร่ใหม่โดย First Party**

## วิธีตรวจ Candidate บนเครื่องพัฒนา

```powershell
.\.venv\Scripts\python.exe scripts\audit_wheelhouse_rights.py --runtime-id vachana --source cache\temp\phasec-vachana-candidate
.\.venv\Scripts\python.exe scripts\audit_wheelhouse_rights.py --runtime-id kokoro --source cache\temp\phasec-kokoro-candidate

powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Check-Portable.ps1 -Json
```

เครื่องมือ Audit อ่าน Wheel เป็น ZIP + Metadata **ไม่ Execute** โค้ดจาก Wheel และไม่ติดตั้งโมเดล ส่วน Report ที่ได้ยังต้องมีผู้ตรวจสอบ **Full License Text, Provenance, Wheel Contents, Native Libraries, Third-party Notices, Redistribution Obligations, Model Weights, Source Revision** ทีละรายการ

## ลิงก์หลักฐานสำหรับตรวจสอบ

- Wayu Inference Code (Apache-2.0): https://github.com/wayu-research/wayu-tts-inference
- Wayu Paxa Edge Model Card / NonCommercial: https://huggingface.co/wayu-ai/wayu-paxa-tts-edge
- Wayu CC BY-NC 4.0: https://creativecommons.org/licenses/by-nc/4.0/legalcode.en
- Vachana Runtime Wheel `vachanatts 0.0.7`: https://pypi.org/project/vachanatts/
- Kokoro Phonemizer GPLv3-or-later: https://pypi.org/project/phonemizer/3.6.0/
- Kokoro ONNX Dependencies: https://pypi.org/project/kokoro-onnx/0.6.0/
- eSpeak NG Loader: https://pypi.org/project/espeakng-loader/0.2.4/

**สิ่งที่ยังต้องทำเพื่อเปลี่ยน HOLD:** ขอหลักฐานอนุญาตที่ชัดเจนจากเจ้าของ Vachana Runtime และเอกสาร License/Notices ที่แจกจริง, วางแผน Compliance ของ GPL/eSpeak/UniDic/OpenJTalk สำหรับ Kokoro (หรือพัฒนาตัวเลือกที่ไม่ต้องใช้ Components เหล่านี้โดยทดสอบเสียงใหม่), และพัฒนา Wayu Offline Build ที่มีซอร์ส/เวอร์ชัน/แฮช/สิทธิ์ของ Dependencies ครบ โดยยังติดป้าย **NC ของน้ำหนักโมเดล** ต่อไปแม้ Offline Build จะสำเร็จก็ตาม
