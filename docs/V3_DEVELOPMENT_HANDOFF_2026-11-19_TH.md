# VoxWeaveTTS v3 — ผลดำเนินงานและจุดรับช่วง (19 พฤศจิกายน 2026)

## ขอบเขตและสถานะ

ทำงานในต้นฉบับจริง `T:\Space\Projects\ProjectsProgram\VoxWeaveTTS` / `funggier/VoxWeaveTTS` บน `main` โดยเริ่มจาก HEAD `3ae5a471a85ef0cbefa64c9ec789f07797c4168d` ซึ่งตรงกับ `origin/main` ในสถานะก่อนเริ่มงาน มีการลบ/แก้ v2 และเพิ่มไฟล์ v3 **จำนวนมากที่ยังไม่ commit** อยู่แล้ว งานรอบนี้แก้เสริมบน WIP เดิมโดยไม่มีการ reset/pull ทับ, ไม่ commit, ไม่ push, ไม่สร้าง Release และไม่แตะ Server ที่เปิดใช้อยู่

### งานที่แก้ในรอบนี้

- `m2m_runtime.py`: แก้ SyntaxError จาก docstring ที่ติดกับ `from __future__`; เปิด log handle หลังตรวจแพ็กเกจ v3 ที่ยืนยันแล้ว ป้องกันไฟล์ค้าง lock บน Windows เมื่อไม่พบแพ็กเกจ
- `portable_doctor.py`: แยกการรายงาน `incomplete` เมื่อไม่มี Core/โมเดล กับ `needs-attention` เมื่อมีโมเดลแต่ Runtime หรือ Hash ผิดพลาดอย่างถูกต้อง
- ปรับ Regression Tests ของ M2M100 Worker, API ยกเลิก v2, Portable Doctor ให้ยึดสัญญา v3 แทนการอ้าง API ที่ลบแล้ว
- ปรับ `tests/model_packages_ui_smoke.cjs` สำหรับการ Preview/Confirm ติดตั้งแบบ Offline, License, การยืนยัน NC, การยกเลิก และการถอนแพ็กเกจ
- แก้คำสถานะ Runtime ที่เพี้ยนเป็น `????` ใน `web/index.html` และข้อความอ้างอิง v2 ที่ไม่ตรงระบบปัจจุบันใน `ai_engine_registry.py`, `m2m_smoke.py`
- สร้าง `scripts/verify_portable_model_packages.py` ใหม่เป็นตัวตรวจ Stage v3 แบบอ่านอย่างเดียว (ของเดิมอ้าง `voxweavetts.model_packages` ซึ่งถูกลบแล้ว)
- เพิ่มตัวเลือก `-StageDirectory` (ใช้ร่วมกับ `-SkipZip`) ใน Builder v3 เพื่อทดลอง Build ลงโฟลเดอร์แยกโดยไม่ทับ `dist\VoxWeaveTTS` เดิม
- เพิ่ม `docs/UNIVERSAL_VWMODEL_V3_TH.md` และหมายเหตุใน README ทั้งสองภาษา แยกสถานะพัฒนา v3 ออกจากประวัติ Release v0.10.3

### หลักฐานทดสอบที่ผ่าน

| รายการ | ผล |
| --- | --- |
| Python `unittest discover`, `PYTHONPATH=src;tests` | **441 tests: OK** |
| JavaScript `tests/*_smoke.cjs` | **35 suites: PASS** |
| Python `compileall` และ Git `diff --check` | **PASS** |
| Build Portable v3 ด้วย `-SkipZip -StageDirectory` | **PASS** |
| ตรวจ Stage ด้วย Python ของ Portable เองและ `--deep` | **PASS** |
| สร้าง WAV จริงจาก MakHam ใน Stage | **PASS**, 24,000 Hz, 2.08 วินาที |
| ติดตั้ง Supertonic 3 v3 ไฟล์เดียวพร้อม Runtime ใน Stage | **PASS** |
| สร้าง WAV อังกฤษจริงจาก Supertonic 3 | **PASS**, 44,100 Hz, 2.91 วินาที |
| ติดตั้ง Melo Chinese ที่ใช้ Runtime ชุดเดียวกับ Supertonic | **PASS** |
| ถอน Supertonic ขณะ Melo ยังใช้งาน Runtime | **PASS**: Runtime ถูกเก็บไว้ |
| ถอน Melo เป็นโมเดลสุดท้ายที่อ้าง Runtime | **PASS**: Runtime ถูกลบ |
| ตรวจ Stage ซ้ำหลังถอนแพ็กเกจเสริม | **PASS** เหลือ MakHam v3 |

Stage สำหรับทดสอบ:

`T:\Space\Projects\ProjectsProgram\VoxWeaveTTS\dist\VoxWeaveTTS-v3-validation-20261119`

การทดสอบไม่ได้แก้ไข `dist\VoxWeaveTTS` รุ่นเดิมหรือ Runtime ที่เปิดในพอร์ตของผู้ใช้งาน และไม่ได้ออก ZIP เผยแพร่ใหม่

### ข้อจำกัดที่ยังไม่ได้ยืนยัน

- ยังไม่ได้ทดสอบ M2M100 v3 ในสภาพแวดล้อมแปลภาษาจริงจากแพ็กเกจ 418M (ต้องเผื่อ RAM/commit) และไม่ได้ทดสอบ FastThaiG2P/Vachana/Wayu ทุกโมเดลจริง
- ไม่ได้ทดสอบด้วยเครื่องปลายทางเครื่องที่สองหรือหลังย้ายโฟลเดอร์บนดิสก์คนละตำแหน่งด้วยชุดโมเดลจริงทั้งหมด (Regression Fixture v3 ผ่านการทดสอบ Relocatable)
- ยังไม่ได้สร้าง ZIP Release v0.11.0 หรืออัปโหลด GitHub เนื่องจาก v3 อยู่ระหว่างพัฒนา และ WIP ใหญ่ก่อนรอบนี้ยังไม่ได้จัดเป็น Commit ที่ตรวจสอบครบทุกแพ็กเกจ
- สิทธิ์ใช้งานเชิงพาณิชย์ของ Third-party Models ต้องผ่านการตรวจแหล่งที่มา/Voice/Training Dataset แยกจากการตรวจ Integrity

### งานต่อจากนี้

1. ตรวจ Safe Migration ของค่าตั้งค่าและ Presets ของผู้ใช้โดยไม่จำเป็นต้องเปิดใช้ไฟล์แพ็กเกจ v2
2. ทดสอบแพ็กเกจ FastThaiG2P และ M2M100 v3 แบบออฟไลน์บน Stage แยก พร้อมตรวจความจำและคืนพื้นที่ทดสอบให้สมบูรณ์
3. เพิ่ม E2E ทดสอบการย้าย Portable จริงทั้ง Core และ Runtime แยกจากกัน (รวม Worker IPC)
4. Audit ข้อมูล License ที่มากับแพ็กเกจและ Third-party Notices ก่อนประกอบ ZIP/Release
5. เมื่อยืนยันทุกชุดแล้ว จึงจัดกลุ่ม Commit โดยไม่กลบ WIP เดิม, Build ZIP, ตรวจ SHA256 และเผยแพร่ Release ใหม่เมื่อมีคำสั่งชัดเจน

ดูแนวทางแพ็กเกจ v3 และคำสั่งการ Build ใน `docs/UNIVERSAL_VWMODEL_V3_TH.md`
