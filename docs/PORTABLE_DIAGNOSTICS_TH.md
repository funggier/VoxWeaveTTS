# Phase E — Portable Doctor และการทดสอบ Runtime หลังย้ายโฟลเดอร์

สถานะ: **Source หลัง v0.10.1** (ยังไม่รวมใน GitHub Release v0.10.1)

เป้าหมายคือแยกว่า Portable ใช้งานได้หรือไม่, โมเดล Native `.vwmodel v2` ใดขาด Runtime, Wheelhouse อยู่ครบแต่ยังไม่ตรวจ SHA-256 หรือไฟล์มีปัญหา และ Runtime ที่สร้างจากโฟลเดอร์เดิมต้องซ่อมหลังย้ายไดรฟ์หรือไม่

## วิธีใช้

เปิด PowerShell ในโฟลเดอร์โปรแกรมที่แตก ZIP แล้ว:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Check-Portable.ps1

# ผลแบบ JSON สำหรับส่งให้ผู้พัฒนาวิเคราะห์/ระบบทดสอบ
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Check-Portable.ps1 -Json

# ตรวจทุกไฟล์ .whl ที่มี Trusted Lock แบบเต็ม: ชนิด ZIP/metadata/SHA-256
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Check-Portable.ps1 -VerifyWheelhouse

# CI: Exit 2 เมื่อ Core หรือโมเดลที่ติดตั้งไว้ยังใช้ไม่ได้
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Check-Portable.ps1 -Strict
```

ไฟล์ `scripts/Check-Portable.ps1` เลือก Python จาก `runtime/python/python.exe` **ภายในโฟลเดอร์** เป็นลำดับแรก (หรือ `.venv/Scripts/python.exe` ใน Development Checkout) ไม่เรียก Python จาก PATH จึงไม่ต้องติดตั้ง Python ลง Windows แยกเพื่อวิเคราะห์

ใช้ API ภายในได้ด้วย: `voxweavetts.portable_doctor.report(root, verify_wheelhouse=False)` ซึ่งส่ง `format=voxweavetts.portable-doctor-v1`, `core`, `models`, `runtimes`, `summary`, `overall_state` เป็นข้อมูลภาษาอังกฤษสำหรับ Parsing

## ความหมายของสถานะ

- `ready`: ในระดับ Manifest, Runtime Metadata และการติดตั้งที่ตรวจสอบได้ตามสถานะ ปัจจัยบางอย่าง (RAM/Windows Pagefile/ภาษา/ความถูกต้องเสียง) ยังต้องทดลองสร้างเสียงจริงแยกต่างหาก
- `needs-attention`: มีโมเดลที่ติดตั้งแต่ Runtime ยังไม่พร้อม หรือมี Manifest ที่ไม่ผ่านการตรวจสอบ
- `incomplete`: Python หลักไม่อยู่ในโฟลเดอร์หรือไม่มีโมเดล Native v2 ที่พร้อมใช้
- `present-unverified`: พบ Wheelhouse ครบจาก File Name/Size/Lock แต่ยังไม่ได้ Hash ไฟล์ทั้งหมด (ห้ามอ้างว่า Verify ผ่านแล้ว)
- `verified-for-inspection`: เปิดอ่าน Wheel ZIP ทุกไฟล์ ตรวจ Metadata และ SHA-256 ตรงตาม First-party Trusted Lock แล้ว **เฉพาะเพื่อวิเคราะห์**; ยังไม่ได้ติดตั้งหรือรับรองสิทธิ์แจกจ่าย
- `hash-mismatch`: พบ Wheelhouse ไม่ตรง SHA-256 ต้องลบ/แทนที่จากแหล่งที่ไว้ใจได้ก่อนติดตั้ง
- `relocated`, `recipe-changed`, `python-abi-mismatch`, `base-python-missing`: Runtime เดิมต้องซ่อมจาก Recipe/Wheelhouse ที่เชื่อถือ และรับการอนุมัติตามหน้า Runtime Registry ก่อนทำจริง
- `recipe-unsupported`: อย่าง Wayu NC ซึ่งต้องใช้ Git/URL และยังไม่มี Verified Offline Wheelhouse จึงไม่ให้เข้าเส้นทาง Trusted Offline Installer
- `not-published`: อย่าง Vachana/Kokoro ซึ่งยังรอตรวจสิทธิ์ของ Dependencies จึงไม่แจก Wheelhouse ที่ยังไม่ผ่านกระบวนการ Review

**ข้อสำคัญ:** MakHam Paradee ที่ติดตั้งอยู่ใน Portable หลักรันด้วย Core Python โดยตรง จึงถือว่าโมเดลนี้พร้อมใช้ได้ แม้ Isolated PyThaiTTS Worker จะยังไม่ถูกติดตั้ง หากลง FastThaiG2P เพิ่ม จึงต้องติดตั้ง Worker ตามระบบของมัน

## ความปลอดภัยและความเป็นส่วนตัว

Doctor เป็น **Read-only**: ไม่เรียก subprocess, ไม่ติดตั้งแพ็กเกจ, ไม่แก้ Model/Runtime/Settings/Cache, ไม่สั่งหยุด Playback, ไม่แตะ Token/Password, ไม่โหลดหรือ Unpickle น้ำหนักโมเดล และไม่เปิดเว็บ ตัวรายงาน JSON ไม่ส่งพาธ Absolute หรือ Secret ออกมาโดยปริยาย ข้อมูลชื่อโมเดล/สิทธิ์เป็น Manifest ที่อยู่ในโปรแกรมอยู่แล้ว

โหมดตรวจ Wheelhouse อ่านข้อมูลทั้งหมดและใช้เวลา/ดิสก์ I/O มากกว่าโหมดปกติ แต่ไม่คัดลอก Wheelhouse สร้าง Runtime หรือทำการลงชื่อว่าโปรแกรมพร้อมใช้งานเอง เมื่อติดตั้งผ่าน UI จริง ระบบ Verified Installer **ยังต้องตรวจไฟล์และติดตั้งแบบ Transactional อีกครั้ง** หากใช้งานบนเครื่องอื่นการตัดสินใจเชื่อถือ Key/Model License ยังคงเป็นความรับผิดชอบของผู้ใช้

## การซ่อมหลังย้ายเครื่อง

ก่อนอื่นใช้ `Check-Portable.ps1` เพื่อทราบ Runtime ที่ผิดพลาด จากนั้นนำ Wheelhouse ที่ตรงเวอร์ชันมาวางใน `runtime/wheelhouse/<id>` ภายใต้โฟลเดอร์ Portable แล้วกลับไปหน้า **ตั้งค่า → Runtime Registry** เลือกตรวจ/ติดตั้งจาก Verified Wheelhouse หลังยืนยันเอง

เส้นทาง `engine_provider_installer.repair` และ `m2m_runtime.repair` ถูกแก้ให้หา `runtime/tools/uv.exe` ใน Portable ก่อนระบบ PATH เพื่อรองรับ Windows ที่ไม่ได้ติดตั้ง uv แยก แต่ Repair จาก Legacy uv Cache ยังต่างจาก Verified Wheelhouse และไม่ได้ผ่านการตรึง Hash ของ Binary ทั้งชุด จึงควรเลือก Verified Wheelhouse เมื่อมีให้ใช้งานและผ่าน License Review แล้ว

## ขอบเขตการทดสอบ

ทดสอบ Unit สำหรับ MakHam ไม่มี Worker, Wayu NC ขาด Worker, Relocated Runtime, Missing Core/UV, Unsafe Symlink, CLI JSON Exit Code, Wheelhouse Hash Tamper และ Repair โดยไม่มี uv ใน PATH; ทุกผลเป็นการตรวจเฉพาะสภาพแวดล้อม ไม่ได้อ้างว่าทำการทดสอบข้ามคอมพิวเตอร์ทางกายภาพแล้ว

**การทดสอบกับโฟลเดอร์ใหม่บนเครื่องเดียวกัน:** แตก Portable v0.10.1 ลงโฟลเดอร์ชั่วคราวและทับเฉพาะโค้ดที่แก้ใน Phase E, แยก Sherpa (3 Wheels) และ PyThaiTTS (26 Wheels) Wheelhouse, จำกัด Windows PATH ไม่ให้พบ uv ภายนอก, ตรวจ SHA-256 ของทุก Wheel, ติดตั้งทั้งสอง Runtime แบบ Offline จริง, เปลี่ยนชื่อโฟลเดอร์ Portable และซ่อมทั้งสองใหม่จาก Verified Wheelhouse สำเร็จโดยไม่แตะ Runtime production นอกจากนี้ Legacy uv-cache repair ของ TTS/M2M100 ตรวจว่า Python ในพาธสุดท้ายเรียกได้และ Dependencies ยังตรงหลัง Activation; หากตรวจไม่ผ่านจะ Rollback กลับไปใช้ Runtime เดิม

การทดสอบ Phase E เพิ่มเติมได้ลอง M2M100 ทั้งโมเดล Native v2 ขนาด 1.9 GB และ Wheelhouse ที่ตรวจสอบแล้วจำนวน 25 Wheels ใน Portable โฟลเดอร์ใหม่ ติดตั้งแบบ Offline → แปลจริง → ย้ายโฟลเดอร์ → ซ่อมจาก Verified Wheelhouse → แปลจริงซ้ำ **สำเร็จครบทุกขั้นตอน**; เครื่องมือทดสอบใช้โฟลเดอร์ชั่วคราวแยกจากข้อมูลจริงและลบได้สำเร็จหลัง Worker ปิดแล้ว (การลบรอบแรกบน Windows ติด Access Denied ชั่วคราว จึงต้องลบซ้ำ)

สำหรับการยืนยัน **M2M100 ว่าแปลจริง** (ไม่ใช่ Read-only Doctor) มีคำสั่งแยกที่ผู้ใช้ต้องเรียกเอง: `scripts/Verify-M2M100Runtime.ps1` ซึ่งจะสร้าง Worker และรันโมเดล CPU จริงสองตัวอย่าง ดู [คู่มือ M2M CPU Validation](M2M100_CPU_RUNTIME_VALIDATION_TH.md)

งานถัดไป: ติดตั้ง Verified Wheelhouse บน **คอมพิวเตอร์ Windows คนละเครื่อง** ที่ไม่มี Developer Tools, ตรวจสิทธิ์ Vachana/Kokoro Dependencies, และทดสอบ M2M100 Translation Inference กับ Pagefile/RAM ที่เพียงพอ
