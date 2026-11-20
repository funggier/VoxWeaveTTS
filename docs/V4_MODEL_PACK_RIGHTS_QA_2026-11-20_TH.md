# VoxWeaveTTS v4 — Model Pack ที่มีเอกสารสิทธิ์ติดตั้งมาด้วย

วันที่: 20 พฤศจิกายน 2026 · สถานะ **QA / ยังไม่เผยแพร่ไฟล์โมเดล v4**

## แนวทางแจกจ่าย

VoxWeaveTTS ไม่ได้มุ่งจำหน่ายโมเดลเชิงพาณิชย์ ผู้พัฒนาตั้งใจแจกไฟล์ `.vwmodel v4` โดย **รักษา License ของโมเดลจากต้นทางตามจริงทุกตัว** และให้ผู้ใช้เลือกติดตั้งแพ็กเกจพร้อม Worker, Model, Dependencies และ Runtime ออฟไลน์ด้วยตนเอง

**โมเดล NonCommercial แจกได้เมื่อใบอนุญาตเดิมอนุญาตและทำตามเงื่อนไขนั้นครบ** จึงไม่มีนโยบายบังคับว่าทุกโมเดลต้องใช้งานเชิงพาณิชย์ได้ Wayu ต้องคง **CC BY-NC 4.0** และข้อกำหนด Acceptable Use ส่วน Supertonic 3 ต้องคง **OpenRAIL-M**

## ผลตรวจเทียบ V2/V3 กับ V4

ได้ตรวจ **13 ไฟล์ที่เคยเผยแพร่บน GitHub จริง** (V2 8 ตัวใน v0.10.3, V3 5 ตัวใน v0.11.0) โดย SHA-256 ของไฟล์ ZIP และน้ำหนักโมเดลรายไฟล์ ภายใน V4 **น้ำหนักโมเดลทุกตัวตรงกับ V2** และ 5 ตัวที่เคยมี V3 ก็ตรงกับ V3 เช่นกัน

ดูรายงาน: [V4_MODEL_LICENSE_CONTINUITY_TH.md](V4_MODEL_LICENSE_CONTINUITY_TH.md) และ [v4_weight_continuity_summary.json](v4_weight_continuity_summary.json)

## ทำแพ็กเกจ V4 รุ่นเพิ่มหลักฐานสิทธิ์แล้ว

สร้างแพ็กเกจ QA ใหม่แยกจากต้นฉบับที่ `dist/ModelPackagesV4-LegalQA/` ครบ **8 ไฟล์** โดยคงโมเดล, Worker, Wheel, Manifest Rights และ Attribution เดิมทุกค่า แล้วเพิ่มสำเนาเอกสาร License/Notice ที่อยู่ใน Wheel ที่ติดตั้งจริง พร้อมดัชนี SHA-256 แยกใน `assets/legal/WHEEL_RIGHTS_INDEX.json`

ผลตรวจ `scripts/verify_v4_legal_packaging.py`:

- 8/8 แพ็กเกจตรงกับ Manifest เดิม
- Wheel **234 รายการรวมตามแพ็กเกจ** มี SHA-256 ตรงกับต้นฉบับทุก Wheel
- เพิ่มเอกสารสิทธิ์/ดัชนี **322 ไฟล์รวม** ลงในแพ็กเกจใหม่
- ไม่แก้เสียง/น้ำหนัก/โค้ด Plugin หรือเงื่อนไข License เดิม
- บาง Wheel ขาด License ใน Metadata ต้นฉบับ; ไม่ได้อ้างว่าได้รับสิทธิ์เพิ่มจากการทำดัชนี

| โมเดล | License โมเดลเดิม | ไฟล์สิทธิ์เพิ่ม | Wheel ยังขาด License Declaration |
| --- | --- | ---: | ---: |
| MakHam Paradee | Apache-2.0 | 36 | 0 |
| FastThaiG2P Thai Som | Apache-2.0 | 36 | 0 |
| Melo Chinese ONNX | MIT | 7 | 0 |
| Supertonic 3 | OpenRAIL-M | 7 | 0 |
| Kokoro Multilingual | Apache-2.0 | 41 | 2 |
| Vachana 4 Voices | MIT | 21 | 1 |
| Wayu Paxa Edge NC | **CC BY-NC 4.0** | 143 | 1 |
| M2M100 418M | MIT | 31 | 1 |

**สิทธิ์ยังค้างที่ส่วนสภาพแวดล้อม** ไม่ได้หมายความว่าน้ำหนักโมเดลใหม่ไม่ตรงต้นฉบับ:

- `espeakng-loader` และ eSpeak-NG Native Library มีเรื่อง License Text/Source และ GPL ที่ต้องทำให้ครบ โดยเฉพาะ Kokoro กับ Wayu
- `vachanatts 0.0.7` ไม่แสดง License Declaration ใน Wheel ต้องตรวจโค้ดและเอกสารต้นทางอย่างเป็นอิสระ
- `sentencepiece 0.2.1` ขาด License Declaration ใน Wheel แต่สำเนา Apache 2.0 จาก Source commit ของผู้เผยแพร่ถูกเก็บไว้ใน `cache/v4-rights-evidence/runtime-sources` แล้ว
- `flatbuffers` ขาด License Text ภายใน Wheel แต่เก็บต้นฉบับ Apache 2.0 จาก Source commit ไว้ในพื้นที่เดียวกันแล้ว
- `sherpa-onnx-core` ขาด License Text ใน Wheel แต่แพ็กเกจ LegalQA Melo และ Supertonic มีสำเนา LICENSE Apache 2.0 ที่อ้างอิง Commit ต้นทางแล้ว
- ONNX Runtime เป็นองค์ประกอบ Native ใน sherpa-onnx-core ต้องแนบประกาศ/License ของไบนารีที่เกี่ยวข้องด้วยก่อนถือว่าพร้อมแจกจ่าย

**GPL/LGPL ไม่ใช่ข้อห้ามใช้เชิงพาณิชย์หรือห้ามแจกจ่ายโดยทั่วไป** แต่การแจกไบนารีอาจต้องแนบ Source ที่ตรงกันและ Notices ตามเงื่อนไข การไม่เน้นการค้าไม่ได้ทำให้เงื่อนไขเหล่านี้หมดไป

## ทดสอบ

บนเครื่องพัฒนา:

~~~powershell
# ตรวจสิทธิ์ใน Wheel โดยอ่านจากไฟล์ที่บรรจุจริง
.\.venv\Scripts\python.exe -X utf8 scripts\audit_v4_wheel_licenses.py

# เปรียบเทียบ V2/V3 กับ v4 โดยตรวจ GitHub Release SHA
.\.venv\Scripts\python.exe -X utf8 scripts\audit_legacy_v4_release_provenance.py

# ประกอบ LegalQA จาก v4 QA (จะไม่เขียนทับไฟล์ที่มีอยู่)
.\.venv\Scripts\python.exe -X utf8 scripts\repackage_v4_with_legal_evidence.py --models melo-chinese-onnx

# ตรวจว่าการประกอบเพิ่มแค่ License และไม่เปลี่ยน Model/Runtime เดิม
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_legal_packaging.py
~~~

**อัปเดต:** ประกอบแพ็กเกจ QA แยกที่ `dist/ModelPackagesV4-NoticeQA/` ใหม่ครบ 8 ตัว โดยให้ตัวประกอบรวม License ต้นฉบับที่ตรึง Revision ของ FlatBuffers/SentencePiece สำหรับแพ็กเกจที่เกี่ยวข้องด้วย พร้อมเก็บชุด `LegalQA` เดิมไว้เทียบ ไม่แก้ Weight/Worker/Wheel หรือ License โมเดลเดิม ดู [V4_DEPENDENCY_NOTICE_QA_2026-11-20_TH.md](V4_DEPENDENCY_NOTICE_QA_2026-11-20_TH.md) สำหรับข้อจำกัด Runtime ที่ต้องตรวจให้ครบก่อนเผยแพร่

**ยังไม่อัปโหลดแพ็กเกจ LegalQA เป็น Public GitHub Release** เพราะการตรวจการแจกจ่ายสภาพแวดล้อมบางรายการยังไม่ครบ ไม่ใช่เพราะจำเป็นต้องซื้อ License เชิงพาณิชย์ของโมเดลทุกตัว
