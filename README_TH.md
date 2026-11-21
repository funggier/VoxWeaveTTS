# VoxWeaveTTS

**Windows Portable TTS Studio v0.12.3 — Universal .vwmodel v4 เท่านั้น**

**Live Pipeline v0.12.3:** เพิ่มสวิตช์ **เตรียมและสร้างเสียงล่วงหน้า** แยกทั้ง 6 โหมด Live โดยกำหนดเพดาน **คิวเตรียม/แปลล่วงหน้า (1–8; เริ่มต้น 3)** และ **คิวเสียงรอเล่น (1–8; เริ่มต้น 2)** ผลรวมไม่เกิน 10 คิว ไม่รวมเสียงที่กำลังเล่นและคิวแชทดิบที่มีระบบสุ่มลดของเดิม เมื่อเปิดระบบจะเตรียมข้อความและสร้างเสียงถัดไปขณะเสียงก่อนเล่นอยู่ แต่ยังเล่นตามลำดับเดิม เมื่อปิดจะกลับไปทำงานแบบเดิม การตั้งค่าแยกแต่ละโหมดและบันทึกได้ ดู [คู่มือและ Release Notes v0.12.3](docs/RELEASE_NOTES_v0.12.3_TH.md)

**Public Release [v0.12.3](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.3) เป็น Core Portable แบบครบชุด (ไม่รวมโมเดล):** แก้ปัญหา [Kokoro และ Wayu ที่ติดตั้งไม่ได้ใน v0.12.1](docs/RELEASE_NOTES_v0.12.2_TH.md) โดยรองรับไฟล์ต้นฉบับ GPL/LGPL ที่แนบอยู่ในแพ็กเกจ V4 ดาวน์โหลด [โมเดล V4 อีก 7 ตัวแยกได้จาก Model Packs Release](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4) โดยคง License เดิมของผู้เผยแพร่ไว้ ส่วน Vachana เก็บเฉพาะในเครื่องและไม่เผยแพร่

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

โมเดลที่ไม่ได้ติดตั้งจะไม่ถูกเปิดใช้งาน **Core ที่เผยแพร่สาธารณะไม่มีโมเดลเริ่มต้น:** ดาวน์โหลด MakHam, FastThaiG2P, Melo, Supertonic, Kokoro, Wayu และ M2M100 ได้จาก [Release โมเดล V4 ทั้ง 7 ตัว](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4) ติดตั้งผ่านไฟล์ `.vwmodel` โดยตรง และยังมีแพ็กเกจ Windows SAPI Desktop v4 แยกจาก [v0.12.1](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1)

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
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Portable.ps1 -Version 0.12.3 -StageDirectory dist\release-v0.12.3\VoxWeaveTTS
.\dist\release-v0.12.3\VoxWeaveTTS\runtime\python\python.exe -X utf8 scripts\verify_v4_core_only_stage.py --stage dist\release-v0.12.3\VoxWeaveTTS
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_core_release_model_compatibility.py --stage dist\release-v0.12.3\VoxWeaveTTS
```

การสร้าง Public Core **ไม่ต้องมีแพ็กเกจโมเดลใด ๆ** และ Build จะปฏิเสธการรวมแพ็กเกจ QA ลงใน ZIP ส่วนการทดสอบภายในสามารถใช้ `-SkipZip -IncludeUnreleasedQaMakHam` แยกจาก Release ได้

ชุดโมเดล QA v4 ทั้งหมดเก็บไว้ในเครื่องที่ `dist/ModelPackagesV4-QA` ไม่ Commit ไฟล์ Weights/Runtime ขึ้น GitHub

## สถานะการเผยแพร่และสิทธิ์

โครงสร้าง Core และแพ็กเกจทั้งหมด **8 ตัว (TTS 7 + Translation 1)** ผ่านการทดสอบใน QA แล้ว และน้ำหนักโมเดล V4 ตรงกับต้นฉบับ V2 ตามหลักฐาน SHA-256 ปัจจุบัน **เผยแพร่โมเดล V4 แบบแยก 7 ตัวแล้ว** (TTS 6 + Translation 1) พร้อมเอกสารสิทธิ์และ Dependencies ออฟไลน์ โดย **Vachana / `vachanatts` ยังคงเก็บเฉพาะในเครื่อง** เพราะสิทธิ์ของตัวโค้ดยังยืนยันไม่ครบ

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
- [Live Pipeline และ Public Release v0.12.3](docs/RELEASE_NOTES_v0.12.3_TH.md)
- [หมายเหตุ Public Release v0.12.2 และการแก้ Kokoro / Wayu](docs/RELEASE_NOTES_v0.12.2_TH.md)
- [หมายเหตุ Model Packs V4 ทั้ง 7 ตัว](docs/RELEASE_NOTES_MODEL_PACKS_V4_SEVEN_TH.md)
- [หมายเหตุ Public Release v0.12.1](docs/RELEASE_NOTES_v0.12.1_TH.md)
- [หมายเหตุ Public Release v0.12.0](docs/RELEASE_NOTES_v0.12.0_TH.md)
- [สำเนาเอกสารสิทธิ์จากผู้เผยแพร่ต้นทาง v4 และ SHA-256](docs/V4_UPSTREAM_LICENSE_EVIDENCE_TH.md)
