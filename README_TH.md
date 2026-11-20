# VoxWeaveTTS

**Windows Portable TTS Studio v0.12.1 — Universal .vwmodel v4 เท่านั้น**

**Public Release v0.12.1 เป็น Core-only:** ตัวโปรแกรม Portable ไม่มีน้ำหนักโมเดลเสียงหรือโมเดลแปลภาษาใน ZIP แต่มีแพ็กเกจแยก **Windows SAPI Desktop v4** สำหรับสร้างเสียงพูดอังกฤษจริงด้วยเสียง SAPI ที่ติดตั้งอยู่ใน Windows ของผู้ใช้ (ไม่แจกไฟล์เสียงของ Microsoft) ติดตั้งจากไฟล์ `.vwmodel` เดียวแบบออฟไลน์ได้ โมเดล QA ทั้ง 8 ตัวที่ต้องแจก Wheel/Runtime ของบุคคลที่สามยังไม่ผ่านเกณฑ์สิทธิ์แจกจ่าย

VoxWeaveTTS เป็นโปรแกรมอ่านข้อความภาษาไทยและหลายภาษาแบบออฟไลน์ มีระบบจัดคิวเสียง ควบคุมเสียง กรองข้อความ แปลภาษา และแสดง Subtitle/Overlay สำหรับ Live ได้ โดยระบบโมเดลแยกจากตัวโปรแกรมหลักอย่างอิสระ

## Universal v4

ผู้ใช้เพียง **กดติดตั้ง → เลือกไฟล์ .vwmodel → ติดตั้งสำเร็จ** ไม่มีหน้าต่างยืนยันสิทธิ์ซ้ำ และไม่มีการดาวน์โหลด Dependencies ระหว่างติดตั้ง การกดติดตั้งถือเป็นการยอมรับเงื่อนไขของแพ็กเกจและเลือกเชื่อถือ Worker ภายนอกนั้น

- **รองรับเฉพาะ .vwmodel format v4:** ไม่มีตัวอ่าน/ติดตั้ง v1, v2, v3 และไม่มีการเรียก Model Adapter รุ่นเก่าจาก Core
- แพ็กเกจมี Model Weights, Worker Plugin, Configurations, Dependencies และ Metadata สิทธิ์ของตัวเองในไฟล์เดียว
- Python 3.11 Worker พร้อม Wheel ออฟไลน์ หรือ Native Worker แบบโปรแกรม .exe ที่มีสภาพแวดล้อมของตัวเอง
- Engine TTS และ Translation ใช้ Worker Protocol ผ่าน JSON Lines โดย Core จัด Queue, Voice Controls, API และ Subtitle Timeline
- ติดตั้ง/ถอนติดตั้งได้ ไม่ต้องเลือก Python หรือรัน Installer ภายนอก
- เก็บ Settings, Models, Cache และ Runtime ในโฟลเดอร์ Portable โดยรองรับการย้ายตำแหน่งโฟลเดอร์
- ตรวจ ZIP, SHA-256, Safe Paths, Size Limits และ Wheel Startup Hooks อัตโนมัติก่อนติดตั้ง

**ข้อจำกัดความปลอดภัย:** การติดตั้งเป็นการเลือกเชื่อถือโค้ด Engine ซึ่งอาจทำงานด้วยสิทธิ์ Windows ของผู้ใช้ การตรวจ SHA-256 ไม่ใช่การรับประกันความปลอดภัยหรือยืนยันผู้เผยแพร่ และการยอมรับของผู้ใช้ไม่ทดแทนสิทธิ์ที่ผู้แจกจ่ายต้องมีใน Model/Dependencies

## รูปแบบการใช้งาน

- **Document / Narration** — อ่านข้อความและเอกสาร, ปรับความเร็ว/ระดับเสียง, พจนานุกรมการอ่าน และ Preset
- **Discord / YouTube LIVE / TikTok LIVE** — รับข้อความและอ่านตามคิว แยกการตั้งค่าของแต่ละโหมด
- **Translation** — กรองข้อความและแปลข้อความต่างภาษา ก่อนเลือก TTS Model ตามภาษาที่อ่าน
- **Queue / Overlay / API** — คิวเสียงและการอ่านพร้อมข้อมูลเหตุการณ์สำหรับ Subtitle/OBS
- **Global Settings** — กฎการอ่าน, การแทนคำ, Emoji, และการจัดการโมเดล/ส่วนเสริม

โมเดลที่ไม่ได้ติดตั้งจะไม่ถูกเปิดใช้งาน **Core ที่เผยแพร่สาธารณะไม่มีโมเดลเริ่มต้น:** MakHam และโมเดลอื่นยังอยู่ในชุด QA ภายใน แต่สามารถดาวน์โหลดแพ็กเกจ Windows SAPI Desktop v4 แยกจาก Release เพื่ออ่านภาษาอังกฤษด้วยเสียงที่ Windows มีอยู่แล้วได้ (ไม่ใช่โมเดล Voice Cloning)

## สำหรับนักพัฒนาแพ็กเกจ

ดู [ตัวอย่างการสร้างแพ็กเกจ v4](examples/README_TH.md) มีตัวอย่าง Python Worker, Offline Wheel, Native EXE, Model TTS และ Translation Worker ซึ่งเป็นตัวอย่างของ v4 เท่านั้น

ใช้ `scripts/build_vwmodel_v4.py` สร้างไฟล์ .vwmodel v4 จาก Source Folder + Spec:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\build_vwmodel_v4.py --source examples\v4-demo-tone --spec examples\v4-demo-tone\spec.json --output cache\demo-tone-v4.vwmodel
```

ดู [คู่มือ Protocol v4](docs/UNIVERSAL_VWMODEL_V4_TH.md) และ [ผลตรวจโมเดลครบ 8 ตัว](docs/V4_ALL_MODEL_QA_TH.md)

## การสร้างและทดสอบ Portable (เครื่องนักพัฒนา)

ใช้ PowerShell บน Windows และ Python Environment ของโปรเจกต์:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Portable.ps1 -Version 0.12.1 -StageDirectory dist\release-v0.12.1\VoxWeaveTTS
.\dist\release-v0.12.1\VoxWeaveTTS\runtime\python\python.exe -X utf8 scripts\verify_v4_core_only_stage.py --stage dist\release-v0.12.1\VoxWeaveTTS
```

การสร้าง Public Core **ไม่ต้องมีแพ็กเกจโมเดลใด ๆ** และ Build จะปฏิเสธการรวมแพ็กเกจ QA ลงใน ZIP ส่วนการทดสอบภายในสามารถใช้ `-SkipZip -IncludeUnreleasedQaMakHam` แยกจาก Release ได้

ชุดโมเดล QA v4 ทั้งหมดเก็บไว้ในเครื่องที่ `dist/ModelPackagesV4-QA` ไม่ Commit ไฟล์ Weights/Runtime ขึ้น GitHub

## สถานะการเผยแพร่และสิทธิ์

โครงสร้าง Core และแพ็กเกจทั้ง **8 ตัว (TTS 7 + Translation 1)** ผ่านการติดตั้ง/Inference จริงในสภาพแวดล้อม QA แล้ว และ **น้ำหนักโมเดลของทั้ง 8 ตัวตรงกับ V2 ที่เคยเผยแพร่ (ตรวจ SHA-256)** จึงนำหลักฐานสิทธิ์ของน้ำหนักโมเดลเดิมมาใช้ต่อได้ ส่วนที่ยังต้องจัดการสำหรับการเผยแพร่ V4 คือ License/Notice ของ **Worker และ Dependencies ออฟไลน์ที่เพิ่มมา** โดยยังไม่มี Public Release ของแพ็กเกจ v4 ทั้ง 8 ตัว

โปรเจกต์นี้ **ไม่ได้มุ่งการใช้งานเชิงพาณิชย์** และจะแจกโมเดลแยกจาก Core **ภายใต้สิทธิ์เดิมของผู้เผยแพร่** โดย Wayu Paxa Edge ยังคงเป็น **CC BY-NC 4.0** พร้อมข้อกำหนด Attribution และ Acceptable Use ไม่จำเป็นต้องตัด Wayu เพียงเพราะมีข้อจำกัด NonCommercial ส่วน Kokoro / Vachana และโมเดลอื่นจะรักษาข้อกำหนด Dependencies ให้ครบ ไม่ตีความว่าการทำงานได้เท่ากับได้รับสิทธิ์แจกจ่ายแล้ว

รุ่นที่เคยเผยแพร่ไว้ก่อนหน้าสามารถดูใน [GitHub Releases](https://github.com/funggier/VoxWeaveTTS/releases) และ Git History แต่ **Source/Portable ที่พัฒนาใหม่รองรับเฉพาะ v4**

โปรเจกต์หลัก: [funggier/VoxWeaveTTS](https://github.com/funggier/VoxWeaveTTS)

## เอกสารที่เกี่ยวข้อง

- [เอกสาร API](docs/API.md)
- [Worker / Model v4](docs/UNIVERSAL_VWMODEL_V4_TH.md)
- [ผลตรวจรับ Core v4-only และ Portable ZIP (20 พฤศจิกายน 2026)](docs/V4_ONLY_QA_HANDOFF_2026-11-20_TH.md)
- [ผลการทดสอบ 8 โมเดล](docs/V4_ALL_MODEL_QA_TH.md)
- [ระบบแปลภาษา](docs/AI_PROCESSING_TRANSLATION_TH.md)
- [การจัดคิวเสียง](docs/LIVE_MESSAGE_QUEUE_TH.md)
- [นโยบายสิทธิ์](docs/COMMERCIAL_LICENSE_POLICY_TH.md)
- [ผลเทียบโมเดล V2/V3/V4 และการคงสิทธิ์เดิม](docs/V4_MODEL_LICENSE_CONTINUITY_TH.md)
- [สถานะ Model Pack v4 พร้อมสำเนา License/Notice ในแพ็กเกจ](docs/V4_MODEL_PACK_RIGHTS_QA_2026-11-20_TH.md)
- [ผลประกอบ V4 พร้อม License ของสภาพแวดล้อม โดยคงสิทธิ์โมเดลเดิม](docs/V4_DEPENDENCY_NOTICE_QA_2026-11-20_TH.md)
- [หมายเหตุ Public Release v0.12.1](docs/RELEASE_NOTES_v0.12.1_TH.md)
- [หมายเหตุ Public Release v0.12.0](docs/RELEASE_NOTES_v0.12.0_TH.md)
- [สำเนาเอกสารสิทธิ์จากผู้เผยแพร่ต้นทาง v4 และ SHA-256](docs/V4_UPSTREAM_LICENSE_EVIDENCE_TH.md)
