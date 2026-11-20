# V4 Model Package — แยกสิทธิ์โมเดลเดิมกับสภาพแวดล้อมที่เพิ่มเข้ามา

วันที่: 20 พฤศจิกายน 2026

## หลักการคงสิทธิ์เดิม

โปรเจกต์ยึดหลัก **ใช้ License เดิมของแต่ละโมเดลที่เคยเผยแพร่ใน V2/V3** และไม่เปลี่ยนสิทธิ์ของน้ำหนักโมเดลเมื่อเปลี่ยนเป็น Universal `.vwmodel v4` โดยน้ำหนักทั้ง 8 ตัวตรงกับ V2 (5 ตัวตรงกับ V3 ด้วย) ตาม SHA-256 ดูรายงาน [V4_MODEL_LICENSE_CONTINUITY_TH.md](V4_MODEL_LICENSE_CONTINUITY_TH.md)

ใน V4 จุดที่เพิ่มจากเดิมคือ **Worker/สภาพแวดล้อม Python/Wheel/Native Binary แบบออฟไลน์ในแพ็กเกจเดียว** ซึ่งมีสิทธิ์ของเจ้าของแต่ละไลบรารีแยกจากสิทธิ์น้ำหนักโมเดล ต้องรักษาเอกสาร Notice, Attribution, Source หรือ Source Offer หากเงื่อนไขต้นทางระบุ ไม่ต้องซื้อสิทธิ์เชิงพาณิชย์ของโมเดล NonCommercial เพื่อแจกแบบไม่ใช่เชิงพาณิชย์เมื่อเงื่อนไขเดิมอนุญาตให้แจก

## แพ็กเกจที่ประกอบเพิ่มเอกสารต้นทาง

สร้างเป็น QA แบบแยกจากไฟล์รุ่นก่อนที่ `dist/ModelPackagesV4-NoticeQA/` ด้วย `scripts/repackage_v4_with_legal_evidence.py --output-dir ... --models ...` ไม่เขียนทับแพ็กเกจเดิม รายการ `assets/legal/WHEEL_RIGHTS_INDEX.json` ระบุ SHA-256 ของ Wheel และสำเนาเอกสารสิทธิ์ที่มาจาก Wheel จริง พร้อม License ที่ตรึง Revision จากต้นทางสำหรับ FlatBuffers, SentencePiece และ sherpa-onnx ที่ Wheel ไม่มีไฟล์เต็ม

| โมเดล | License ของน้ำหนักเดิม | Wheel ใน V4 | License Declaration ของ Wheel ที่ยังขาด |
| --- | --- | ---: | ---: |
| MakHam Paradee | Apache-2.0 | 26 | 0 |
| FastThaiG2P Thai Som | Apache-2.0 ตามประกาศแพ็กเกจเดิม | 26 | 0 |
| Melo Chinese ONNX | MIT | 3 | 0 |
| Supertonic 3 | OpenRAIL-M | 3 | 0 |
| Kokoro 82M | Apache-2.0 | 31 | 2 |
| Vachana Thai 4 Voices | MIT ตาม Model Card | 14 | 1 |
| Wayu Paxa Edge NC | **CC BY-NC 4.0** และ Acceptable Use | 106 | 1 |
| M2M100 418M | MIT ตาม Model Card | 25 | 1 |

จำนวน Wheel ทั้งแปดแพ็กเกจรวม **234 รายการตามแพ็กเกจ** (บาง Wheel ถูกใช้ซ้ำระหว่างแพ็กเกจ) การไม่มี License Declaration ใน Wheel ไม่ได้พิสูจน์ว่าไม่มีใบอนุญาตหรือให้สิทธิ์แจกจ่ายตาม SPDX อื่นได้

## ความคืบหน้า: ตรวจ Native DLL ลงถึง SHA-256 และเก็บซอร์ส GPL

มีรายงานรอบต่อเนื่อง [V4_NATIVE_COMPONENT_EVIDENCE_2026-11-20_TH.md](V4_NATIVE_COMPONENT_EVIDENCE_2026-11-20_TH.md) ซึ่งตรวจไฟล์ Native จริงใน Wheel ทั้ง 137 ชุดไม่ซ้ำ โดยพบ 400 ไบนารีไม่ซ้ำตาม SHA-256 เพิ่มหลักฐานต้นฉบับของ ONNX Runtime 1.28.2 สำหรับ Melo/Supertonic และเก็บซอร์ส eSpeak NG 1.52.0, GPL License และ Build Workflow สำหรับ Kokoro/Wayu ในแพ็กเกจ QA แยกโดยไม่แก้ไฟล์โมเดล/Worker/Wheel เดิม

**สถานะเผยแพร่ยังไม่เปลี่ยน:** นี่เป็น QA เพื่อเตรียมทำตามหน้าที่ของผู้แจกจ่ายไบนารี ไม่ใช่การยืนยันความครบของ Native Notices และ Corresponding Source ทุกตัว

## สิ่งที่ยืนยันแล้วและสิ่งที่ยังต้องตรวจ

**ยืนยันด้านเทคนิคได้:** โมเดล น้ำหนัก Worker และ Wheel ทั้งชุดไม่เปลี่ยน SHA-256 เทียบ QA ดั้งเดิม การเพิ่มเอกสารสิทธิ์เป็นไฟล์ใหม่เท่านั้น และ Universal v4 ติดตั้ง/ทำ Inference/ถอนติดตั้งแบบออฟไลน์ได้บนเครื่องพัฒนา

**ยังไม่ใช่การอนุมัติเผยแพร่:** สำหรับ V4 ที่บรรจุ Runtime ใหม่ ต้องตรวจประกาศที่ครบของไลบรารี Native/Third-Party อีกครั้ง; โดยเฉพาะ `sherpa-onnx-core` (รวม ONNX Runtime), `espeakng-loader` และ eSpeak-NG GPLv3+ ที่ต้องจัด Corresponding Source/Notices ให้ครบ; `vachanatts 0.0.7` ไม่มี License โค้ดใน Wheel ที่พิสูจน์สิทธิ์แจกต่อได้เพียงพอ; Kokoro/Wayu มีส่วนของ phonemizer (GPL) และ Wayu มี LGPL Dependencies; และ `tokenizers` กับ `sentencepiece` บางไฟล์ต้องอ้าง License/Native Notices ต้นทางเพิ่มเติม

**สถานะของแพ็กเกจแปดตัวนี้:** ชุด `NoticeQA` เป็นไฟล์ **ทดสอบภายใน ยังไม่ขึ้น GitHub Release** จนการตรวจสิทธิ์ของสภาพแวดล้อมที่เพิ่มใน V4 ครบ ชุดไฟล์เหล่านี้ต้องไม่เปลี่ยนหรืออ้างว่าได้รับสิทธิ์ใหม่เป็น MIT โดยพลการ

เรื่องนี้ไม่ใช่การปฏิเสธใช้โมเดล NC หรือบังคับให้โมเดลใช้เชิงพาณิชย์ได้ แต่เป็นการทำให้ไฟล์ที่เพิ่มเข้ามาจากผู้เผยแพร่รายอื่นทำตามข้อกำหนดของตัวเองอย่างถูกต้อง

อ่านเพิ่มเติม: [V4_MODEL_PACK_RIGHTS_QA_2026-11-20_TH.md](V4_MODEL_PACK_RIGHTS_QA_2026-11-20_TH.md), [V4_UPSTREAM_LICENSE_EVIDENCE_TH.md](V4_UPSTREAM_LICENSE_EVIDENCE_TH.md) และ [V4_RIGHTS_REVIEW_TH.md](V4_RIGHTS_REVIEW_TH.md)
