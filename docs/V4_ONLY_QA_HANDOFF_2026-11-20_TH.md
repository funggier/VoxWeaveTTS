# VoxWeaveTTS v4-only — QA / Development Handoff

วันที่: 20 พฤศจิกายน 2026
สถานะ: **พัฒนา Core v4-only สำเร็จและผ่าน QA แต่ยังไม่ได้ออก Public Release**

## สิ่งที่เปลี่ยนใน Core

- การติดตั้ง/ตรวจ ZIP/ถอนแพ็กเกจ และการค้นหาโมเดล ใช้ Universal `.vwmodel format v4` เท่านั้น
- ตัด Universal v3 reader, v3 installer, v3 runtime, Model Adapter เฉพาะโมเดลที่อยู่ใน Core, v3 Build และ v3 UI ออกจาก Source และ Portable ใหม่
- ใช้ `plugin/worker.py` หรือ Native Worker จากแพ็กเกจ v4 โดยไม่ต้องแก้ Core เมื่อจะเพิ่มสถาปัตยกรรมโมเดลใหม่
- แพ็กเกจมี Dependencies/Wheel แบบออฟไลน์ และติดตั้งแยก Runtime ต่อแพ็กเกจ
- Portable แยกไลบรารี TTS/ML (PyThaiTTS, ONNX Runtime, Kokoro, Sherpa, NumPy, SciPy, PyTorch ฯลฯ) ออกจาก Python Core; โมเดลเริ่มต้น MakHam ถูกติดตั้งจากแพ็กเกจ v4 ระหว่าง Build
- Native File Picker + ปุ่มติดตั้งครั้งเดียวเป็นการยอมรับสิทธิ์และโค้ด Plugin ตามที่ผู้ใช้กำหนด ไม่มี License Server หรือการซ่อมอัตโนมัติ
- เก็บเฉพาะตัวอย่างการสร้างแพ็กเกจ v4 ในโฟลเดอร์ `examples/` ไม่มีตัวอย่าง v3 ปะปน
- ระบบ AI Translation ผ่าน Ollama ยังคงเป็นบริการแยกจากระบบ Model Package v4; โมเดล M2M100 แปลผ่าน Worker v4 ในแพ็กเกจ

## การทดสอบที่ผ่าน

- Python regression: **400 tests, OK**
- JavaScript browser smoke tests: **35 suites, 0 failures**
- v4 model QA ทั้ง **8 แพ็กเกจ**: ติดตั้งออฟไลน์ → ประมวลผลจริง → ถอนติดตั้งสำเร็จ
  - MakHam — ภาษาไทย, 24,000 Hz, อยู่ใน Portable เป็นโมเดลเริ่มต้น
  - FastThaiG2P Thai Som — ภาษาไทย, 24,000 Hz
  - Melo Chinese ONNX — ภาษาจีน, 44,100 Hz
  - Supertonic 3 — อังกฤษ, 44,100 Hz
  - Kokoro — อังกฤษและญี่ปุ่น, 24,000 Hz
  - Vachana 4 Voices — ภาษาไทย, 22,050 Hz
  - Wayu Paxa Edge NC — ภาษาไทย, 24,000 Hz; Runtime มี 106 Wheel
  - M2M100 418M — แปลอังกฤษ→ไทยและไทย→อังกฤษจริง (คุณภาพคำแปลยังต้องปรับ)
- ทดสอบบน **Core v4-only Portable ที่ไม่มีโมดูล v3 และไม่มีไลบรารี ML ใน Core**
- Deep v4 Package QA Audit: ครบ 8, SHA-256 ทุกไฟล์ตรงกัน, ไม่มี Missing/Issues
- Deep v4 Portable Doctor: Ready, Default MakHam v4, `v3_package_support=false`
- ตรวจ ZIP: CRC ผ่าน, ไม่มี v3 ในรายการไฟล์, ไม่มีข้อมูลผู้ใช้/Log, แตกลงโฟลเดอร์ใหม่และสร้าง WAV จริงได้
- **Relocatable แบบย้ายทั้งโฟลเดอร์ผ่านจริง**: ติดตั้ง FastThaiG2P v4 ออฟไลน์ สร้างเสียงไทยก่อนย้ายและหลังย้าย (24,000 Hz, 68,160 frames ทั้งสองครั้ง) โดยไม่ติดตั้ง Runtime ซ้ำ; ถอน FastThaiG2P หลังย้ายสำเร็จและคง Runtime ร่วมที่ MakHam ยังใช้งานอยู่
- เพิ่ม Regression Tests ตรวจว่า Worker Python และ Native Worker ในแพ็กเกจ v4 ใช้ตำแหน่งใหม่หลังย้าย ไม่มีการผูกพาธไว้กับตำแหน่งเดิม

## ไฟล์ QA ที่สร้างในเครื่อง

- `dist/ModelPackagesV4-QA/` — แพ็กเกจ v4 ที่มี `UNRELEASED-QA` ครบ 8 ตัว (ไม่เผยแพร่สาธารณะ)
- `dist/ModelPackagesV4-QA/CATALOG-v4-QA.json` — ขนาด, SHA-256, รายการสิทธิ์ QA (ไม่ได้อนุมัติเผยแพร่)
- `dist/v4-qa-build/VoxWeaveTTS/` — Portable v4-only สำหรับ Build
- `dist/VoxWeaveTTS-v4-clean-validation-20261120/` — Portable v4-only ที่ใช้ทดสอบการติดตั้ง/ถอนโมเดลเสริม
- `dist/VoxWeaveTTS-v0.12.0-dev0-portable.zip` — ZIP สำหรับ QA ภายในเท่านั้น
  - ขนาด: **324,529,596 bytes** (ประมาณ 309.5 MiB)
  - SHA-256: `c315a6676007d4086e08979a191207d5c75c9b284f34635e9b77585f4950a01c`

## สิ่งที่ยังต้องทำก่อน Public Release

1. ตรวจสิทธิ์แจกจ่าย **น้ำหนักโมเดลและทุก Wheel/Native Dependency** รายโมเดล รวมเอกสาร Attribution และการใช้งานเชิงพาณิชย์ (ตรวจ Metadata ของ Wheel ทั้ง 234 รายการ/137 ไฟล์ไม่ซ้ำกันเบื้องต้นแล้ว — ดู [รายงานตรวจสิทธิ์ v4](V4_RIGHTS_REVIEW_TH.md); ยังไม่อนุมัติเผยแพร่)
2. Wayu Paxa Edge ใช้เงื่อนไข NonCommercial (CC BY-NC 4.0) จึงยังไม่อนุญาตให้นำไปเผยแพร่เป็นโมเดลเชิงพาณิชย์
3. Kokoro และ Vachana ยังมีข้อจำกัดและเอกสารสิทธิ์ Runtime ที่ต้องตรวจเพิ่ม; Supertonic 3 เป็น OpenRAIL-M ซึ่งมีเงื่อนไข ไม่ใช่ MIT
4. แยกการอนุมัติสิทธิ์ที่แท้จริงออกจากการติดตั้ง: ผู้ใช้กดติดตั้งได้ ไม่ได้แปลว่าผู้พัฒนามีสิทธิ์แจกจ่าย
5. ตรวจการใช้งานด้วยผู้ใช้จริงต่อเนื่อง (Live Queue, Discord/YouTube/TikTok) และทดสอบแบบ Relocatable ทุกแพ็กเกจเพิ่มเติมเมื่อพร้อม

**ข้อควรระวัง:** โค้ด v3 ถูกลบจาก Source/Build ใหม่แล้ว แต่ข้อมูลที่เหลืออยู่ในโฟลเดอร์เก่าของเครื่องพัฒนา/โปรแกรมที่อาจกำลังรันอยู่ไม่ได้ถูกลบโดยอัตโนมัติ เพื่อไม่รบกวนเซสชันเดิมและเก็บหลักฐานการตรวจสิทธิ์ก่อนทำความสะอาดข้อมูลถาวร

Git History และ Public Release รุ่นก่อนเป็นประวัติย้อนหลัง ไม่เปลี่ยนแปลง และ **ยังไม่มีการเผยแพร่ v4 QA Assets เป็น Public Release**
