# Universal .vwmodel v3 — สถาปัตยกรรมและวิธีใช้งาน (Development)

> สถานะ: รองรับการแจกจ่ายครั้งแรกใน **v0.11.0** (Windows x64 / Python 3.11) · ดาวน์โหลดแพ็กเกจ v3 แยกจากรุ่นเก่า อ่าน [Release Notes](RELEASE_NOTES_v0.11.0.md) สำหรับข้อจำกัดและสิทธิ์โมเดล

## หลักการ

Universal v3 เป็นรูปแบบแพ็กเกจโมเดล **ไฟล์เดียว** ที่ติดตั้งออฟไลน์โดยเลือก `.vwmodel` จากเครื่องผู้ใช้ ข้างในมีไฟล์น้ำหนักโมเดล, Manifest, รายการ Asset, ข้อมูลสิทธิ์/ที่มา และสำหรับโมเดลที่ต้องใช้ Dependencies แยก จะมี Wheel ทั้งชุดและ Lockfile ตรึง SHA-256 ภายในแพ็กเกจ ผู้ใช้ไม่ต้องดาวน์โหลดส่วนประกอบจากเซิร์ฟเวอร์ระหว่างติดตั้ง

- แพ็กเกจมีรูปแบบ `voxweavetts.model-package`, `format_version: 3` เท่านั้น ระบบติดตั้ง **ไม่ยอมรับ v1/v2 และไม่ fallback** ไปยังโค้ดเก่า
- รายชื่อ Adapter ที่รันได้กำหนดไว้ในโค้ดหลัก โปรแกรม **ไม่โหลด Python/EXE/DLL/สคริปต์ติดตั้งจากไฟล์โมเดล** ผู้ผลิตแพ็กเกจไม่สามารถขอสิทธิ์รันคำสั่งอิสระด้วย Manifest
- Wheel ที่เป็น executable dependency ต้องมีค่า SHA-256 ตรงกับ Trusted Lock ที่ผู้พัฒนาแอปบรรจุไว้ใน `scripts/wheelhouse-locks` การใส่ SHA ของตัวเองใน Manifest เพียงอย่างเดียว **ไม่ถือเป็นการอนุมัติให้รันโค้ด**
- จำกัดแพลตฟอร์มปัจจุบันเป็น Windows x64, Python 3.11 และ CPU สำหรับ Native Runtime ของ v3 การเพิ่มแพลตฟอร์ม/Accelerator ต้องเพิ่มการตรวจความเข้ากันได้ ไม่ใช้การดาวน์โหลดอัตโนมัติ
- ใช้ Runtime แยกตาม **fingerprint ของชุด dependencies** ภายใต้ `runtime/environments` สองโมเดลที่ใช้ชุดเดียวกันสามารถแชร์ Runtime ได้ ส่วนโมเดลที่ต้องใช้ชุดต่างกันจะถูกแยกออกจากกัน
- พาธ Runtime/โมเดลอ้างอิงจากโฟลเดอร์โปรแกรมปัจจุบัน ไม่ฝัง Absolute Path ของเครื่องสร้างแพ็กเกจ การย้ายโฟลเดอร์ Portable พร้อม Runtime ที่สมบูรณ์จึงควรใช้ได้โดยไม่ติดตั้งใหม่

## ขั้นตอนติดตั้งสำหรับผู้ใช้

1. เปิดหน้า **Model Package Manager** แล้วเลือกไฟล์ `.vwmodel` v3 เพียงไฟล์เดียวผ่าน File Picker ของ Windows
2. โปรแกรมตรวจรูปแบบ/Manifest และแสดงชื่อแพ็กเกจ, รุ่น, License, Attribution, สถานะสิทธิ์ และคำเตือนว่าติดตั้งแบบออฟไลน์
3. กด **ยอมรับ** เพื่อยืนยันการติดตั้ง หาก License เป็น NonCommercial จะมีการยืนยันข้อจำกัด NonCommercial **แยกต่างหาก**
4. โปรแกรมตรวจไฟล์เดิมซ้ำก่อนเริ่มติดตั้ง, ตรวจ SHA-256 ของ Asset/Wheel, ติดตั้ง Dependencies จาก Wheel ที่ได้รับอนุมัติลงพื้นที่แยก และเปิดใช้โมเดลเมื่อ Runtime พร้อม
5. ถ้าไม่สำเร็จ ระบบต้องไม่ถือว่าโมเดลติดตั้งสำเร็จ และต้องไม่ปล่อยข้อมูล Staging ที่ไม่สมบูรณ์เป็นโมเดลใช้งานได้

**ไม่ต้องต่ออินเทอร์เน็ต**, ไม่ต้องตรวจ Server License และไม่มีการดาวน์โหลด/Repair เป็นส่วนหนึ่งของขั้นตอน v3 ชุดนี้ หาก Runtime ผิดพลาด ให้ถอนโมเดลและติดตั้งไฟล์เดิมใหม่ การถอน Runtime ที่แชร์กันเกิดขึ้นได้เมื่อไม่เหลือโมเดลใดอ้างอิงอยู่แล้วเท่านั้น

การถอนติดตั้งปฏิเสธเมื่อพบไฟล์ที่ผู้ใช้เพิ่มเองหรือไฟล์ Asset ที่ถูกแก้ไข เพื่อป้องกันการลบข้อมูลผู้ใช้โดยไม่ตั้งใจ

## เนื้อหาภายในแพ็กเกจ

ไฟล์ `manifest.json` ประกอบด้วย `format`, `format_version`, `package`, `adapter`, `runtime`, `assets`, `rights`, `files` และ `capabilities`

- `manifest-assets.json` ระบุ Asset ทุกชิ้น (ไม่รวมไฟล์ Manifest/Rights/Lock ที่ระบบจัดการแยก)
- `legal/rights.json` ระบุ SPDX License, URL, Attribution, review_status และแหล่งที่มา
- `runtime/locks/*.lock` ระบุ `requirements` และ `wheels` ของ Runtime แบบ Hash-pinned
- `runtime/wheels/*.whl` มี Wheel ทั้งหมดที่ต้องติดตั้งแบบ Offline ไม่ใช่เพียงรายการให้ไปดาวน์โหลดต่อ
- โมเดล MakHam ที่บรรจุมากับ Core ใช้ `core-bundled` และไม่ต้องมี Wheel แยก

ไฟล์ `.vwmodel` รุ่นก่อนหน้าและโฟลเดอร์โมเดล v2 เดิม **ไม่ถูกใช้งานใน v3 และไม่ถูกลบอัตโนมัติ** ผู้ใช้สามารถสำรองข้อมูลเดิมเองก่อนย้ายระบบ

## การ Build และตรวจสอบ

ใช้โปรเจกต์จริงที่โฟลเดอร์ราก:

```powershell
# build v3 ในพื้นที่ตรวจสอบแยก (ไม่เขียนทับ dist\VoxWeaveTTS เดิม)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Portable-V3.ps1 `
  -SkipZip -StageDirectory "T:\Space\Projects\ProjectsProgram\VoxWeaveTTS\dist\VoxWeaveTTS-v3-validation-20261119"

# ตรวจความครบถ้วนแบบอ่านอย่างเดียว
$stage = "T:\Space\Projects\ProjectsProgram\VoxWeaveTTS\dist\VoxWeaveTTS-v3-validation-20261119"
& "$stage\runtime\python\python.exe" -X utf8 scripts\verify_portable_model_packages.py --stage "$stage" --deep

# ทดสอบ Python
$env:PYTHONPATH = "src;tests"
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'

# ทดสอบ JavaScript
Get-ChildItem tests\*_smoke.cjs | ForEach-Object {
  node $_.FullName
  if ($LASTEXITCODE -ne 0) { throw "Smoke test failed: $_" }
}
```

สำหรับ Build ZIP ของจริงใช้ `scripts/Build-Portable.ps1` ซึ่งเรียก v3 builder โดยตรง แต่อย่าเผยแพร่ไฟล์ทดสอบหรือโมเดลเสริมโดยไม่ตรวจเงื่อนไขสิทธิ์การเผยแพร่แยกต่างหาก

## ข้อจำกัดและงานต่อเนื่อง

- การผ่าน Hash/Manifest/Portable Doctor เป็นการตรวจ **Integrity และความพร้อมของโครงสร้าง** ไม่ยืนยันคุณภาพเสียงหรือสิทธิ์เชิงพาณิชย์
- สิทธิ์ของโมเดล, เสียง, ข้อมูลฝึก, โค้ด และ Wheel ต้องตรวจแยกกัน ห้ามนำสถานะ `cleared` ที่ผู้สร้างแพ็กเกจระบุเองมาใช้เป็นหลักฐานสิทธิ์เผยแพร่
- ต้องทดสอบเสียงจริงด้วย Native Engine ของแต่ละโมเดลและทดสอบ Portable หลังย้ายไปพาธอื่นบน Windows เครื่องปลายทาง
- ชุดโมเดลเสริม เช่น Wayu NC มีข้อจำกัด NonCommercial และต้องแจกจ่ายเป็นแพ็กเกจแยกตามสิทธิ์

เอกสารรุ่นก่อนหน้าใน `docs/*V2*.md` และ Release Notes เก็บไว้เป็นประวัติ ไม่ใช่สัญญาการติดตั้งของ v3
