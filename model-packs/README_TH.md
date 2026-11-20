# Universal .vwmodel v4 — VoxWeaveTTS Model Packages

**รองรับเฉพาะ v4 ใน Source และ Portable รุ่นใหม่** โดย Model/Worker/Dependencies ถูกบรรจุมาในไฟล์ .vwmodel เดียว ผู้ใช้เลือกไฟล์และกดติดตั้งเพื่อใช้งาน ไม่ต้องติดตั้ง Runtime ด้วยตนเอง

ระบบภายในแยก Runtime ของแพ็กเกจ, ตรวจ SHA-256 และ Wheel, เรียก Worker ผ่าน Protocol v1 สำหรับ TTS หรือ Translation และรองรับการย้ายโฟลเดอร์ Portable

โมเดล v4 ที่ผ่าน QA ทั้ง 8 รายการ:

| โมเดล | ประเภท | สถานะการทดสอบ | การแจกจ่าย |
| --- | --- | --- | --- |
| MakHam Paradee | TTS | เสียงไทยผ่าน | ตรวจสิทธิ์เพิ่ม |
| FastThaiG2P Thai Som | TTS | เสียงไทยผ่าน | ตรวจสิทธิ์เพิ่ม |
| Melo Chinese ONNX | TTS | เสียงจีนผ่าน | ตรวจสิทธิ์เพิ่ม |
| Supertonic 3 | TTS | เสียงอังกฤษผ่าน | OpenRAIL-M / ตรวจเงื่อนไข |
| Kokoro 82M | TTS | อังกฤษและญี่ปุ่นผ่าน | HOLD: GPL/Native Notices |
| Vachana Thai 4 Voices | TTS | เสียงไทยผ่าน | HOLD: vachanatts Wheel |
| Wayu Paxa Edge NC | TTS | เสียงไทยผ่าน | HOLD / CC BY-NC 4.0 |
| M2M100 418M | Translation | EN→TH และ TH→EN ผ่าน | ตรวจสิทธิ์เพิ่ม |

ไฟล์ QA อยู่ใน `dist/ModelPackagesV4-QA` ของเครื่องพัฒนา ไม่อยู่ใน GitHub Release เนื่องจากยังไม่ได้ตรวจสิทธิ์ Redistribute ครบ

สร้างตัวอย่างแพ็กเกจใหม่ด้วย `scripts/build_vwmodel_v4.py` และใช้ [ตัวอย่างสำหรับนักพัฒนา v4](../examples/README_TH.md) ดู [คู่มือ v4](../docs/UNIVERSAL_VWMODEL_V4_TH.md) และ [บันทึก QA ทั้ง 8 ตัว](../docs/V4_ALL_MODEL_QA_TH.md)

เก็บหลักฐาน Attribution ของผู้ผลิตต้นทางไว้ใน `model-packs/fastthaig2p` และ `model-packs/vachana` เพื่อใช้ตรวจสิทธิ์ภายหลัง การนำโมเดลมาทดสอบสำเร็จไม่ใช่ใบอนุญาตให้แจกต่อหรือใช้เชิงพาณิชย์
