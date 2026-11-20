# Universal .vwmodel v4 — VoxWeaveTTS Model Packages

**นโยบายของโครงการ:** แจกแพ็กเกจโมเดลเป็นไฟล์แยกจาก Core โดยใช้ License เดิมของผู้เผยแพร่โมเดล ไม่เปลี่ยนสิทธิ์เพื่อให้ใช้เชิงพาณิชย์ ตัวโปรเจกต์ไม่ได้มุ่งจำหน่ายโมเดล และ **Wayu CC BY-NC 4.0 ไม่ถูกตัดออกเพียงเพราะเป็น NonCommercial** แต่การแจกจ่ายต้องปฏิบัติตาม Attribution และ Acceptable Use ตามต้นทางด้วย

ตรวจยืนยันแล้วว่าน้ำหนักโมเดล V4 **ทั้ง 8 ตัวเหมือนกับไฟล์ที่เผยแพร่ใน V2 ด้วย SHA-256** (5 ตัวตรงกับ V3 ด้วย) ดังนั้นงานตรวจเพิ่มเติมเน้น Worker และ Wheel/Native Dependencies ที่เพิ่มมาสำหรับติดตั้งออฟไลน์ ดู [รายงานเทียบ V2/V3/V4 และสิทธิ์ต้นทาง](../docs/V4_MODEL_LICENSE_CONTINUITY_TH.md) และ [ชุด QA พร้อม License ของ Dependencies เพิ่มเติม](../docs/V4_DEPENDENCY_NOTICE_QA_2026-11-20_TH.md) รวมถึง [รายงาน SHA-256 ของ Native DLL และต้นฉบับ GPL/ONNX Runtime](../docs/V4_NATIVE_COMPONENT_EVIDENCE_2026-11-20_TH.md) และ [รายงาน ONNX Runtime 1.31.1 กับ Vachana PyPI Source](../docs/V4_RUNTIME_SOURCE_PROVENANCE_2026-11-20_TH.md) และ [การเทียบ License หลักว่าเข้ากับ Core MIT ได้อย่างไร](../docs/V4_PRIMARY_LICENSE_COMPATIBILITY_2026-11-20_TH.md)

**รองรับเฉพาะ v4 ใน Source และ Portable รุ่นใหม่** โดย Model/Worker/Dependencies ถูกบรรจุมาในไฟล์ .vwmodel เดียว ผู้ใช้เลือกไฟล์และกดติดตั้งเพื่อใช้งาน ไม่ต้องติดตั้ง Runtime ด้วยตนเอง

ระบบภายในแยก Runtime ของแพ็กเกจ, ตรวจ SHA-256 และ Wheel, เรียก Worker ผ่าน Protocol v1 สำหรับ TTS หรือ Translation และรองรับการย้ายโฟลเดอร์ Portable

โมเดล v4 ที่ผ่าน QA ทั้ง 8 รายการ โดย **เผยแพร่สาธารณะ 7 ตัว** และเก็บ Vachana ไว้ในเครื่องพัฒนา:

| โมเดล | ประเภท | สถานะการทดสอบ | การแจกจ่าย |
| --- | --- | --- | --- |
| MakHam Paradee | TTS | เสียงไทยผ่าน | Public V4 · Apache-2.0 |
| FastThaiG2P Thai Som | TTS | เสียงไทยผ่าน | Public V4 · Apache-2.0 |
| Melo Chinese ONNX | TTS | เสียงจีนผ่าน | Public V4 · MIT |
| Supertonic 3 | TTS | เสียงอังกฤษผ่าน | Public V4 · OpenRAIL-M ตามเงื่อนไข |
| Kokoro 82M | TTS | อังกฤษและญี่ปุ่นผ่าน | Public V4 · Apache-2.0 น้ำหนัก / GPL Source Runtime |
| Vachana Thai 4 Voices | TTS | เสียงไทยผ่าน | เฉพาะในเครื่อง · ไม่เผยแพร่โค้ด vachanatts |
| Wayu Paxa Edge NC | TTS | เสียงไทยผ่าน | Public V4 · CC BY-NC 4.0 (NonCommercial เท่านั้น) |
| M2M100 418M | Translation | EN→TH และ TH→EN ผ่าน | Public V4 · MIT |

ไฟล์ QA ทั้ง 8 ยังคงอยู่ใน `dist/ModelPackagesV4-QA` ของเครื่องพัฒนาแยกจากไฟล์เผยแพร่ โดยไฟล์ Public V4 ทั้ง 7 (ไม่รวม Vachana) เตรียมไว้ใน `dist/ModelPackagesV4-PublicSeven` และแจกจ่ายผ่าน [Release V4 Model Packs (7 Models)](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4) พร้อม [รายละเอียด License และเอกสารต้นทาง](../docs/RELEASE_NOTES_MODEL_PACKS_V4_SEVEN_TH.md)

สร้างตัวอย่างแพ็กเกจใหม่ด้วย `scripts/build_vwmodel_v4.py` และใช้ [ตัวอย่างสำหรับนักพัฒนา v4](../examples/README_TH.md) ดู [คู่มือ v4](../docs/UNIVERSAL_VWMODEL_V4_TH.md) และ [บันทึก QA ทั้ง 8 ตัว](../docs/V4_ALL_MODEL_QA_TH.md)

เก็บหลักฐาน Attribution ของผู้ผลิตต้นทางไว้ใน `model-packs/fastthaig2p` และ `model-packs/vachana` เพื่อใช้ตรวจสิทธิ์ภายหลัง การนำโมเดลมาทดสอบสำเร็จไม่ใช่ใบอนุญาตให้แจกต่อหรือใช้เชิงพาณิชย์
