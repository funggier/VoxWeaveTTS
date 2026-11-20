# Universal .vwmodel v4 — ใช้สิทธิ์เดิมของโมเดล และเปรียบเทียบกับ Release V2/V3

สถานะการตรวจ: 20 พฤศจิกายน 2026

## นโยบายของโครงการ

VoxWeaveTTS เป็นเครื่องมือท้องถิ่นเพื่อการทดลองและการใช้งานทั่วไป **ไม่ได้เน้นการจำหน่ายเชิงพาณิชย์** การแจกจ่ายโมเดลแยกจากโปรแกรม Core และเก็บเงื่อนไขจากผู้สร้าง/ผู้เผยแพร่ต้นทางไว้ครบถ้วน ไม่เปลี่ยน CC BY-NC เป็น MIT หรือเปลี่ยน OpenRAIL-M เป็น Apache-2.0

**ไม่จำเป็นต้องคัดโมเดลออกเพียงเพราะต้นทางจำกัดการใช้เชิงพาณิชย์** หากสิทธิ์เดิมอนุญาตให้แจกจ่ายแบบไม่ใช่เชิงพาณิชย์ โมเดลนั้นอาจเผยแพร่ภายใต้เงื่อนไข NonCommercial/Attribution เดิมได้ แต่การบรรจุ Worker, Wheel และ Native Library เพิ่มใน v4 เป็นการแจกจ่ายซอฟต์แวร์บุคคลที่สามเพิ่มเติม ซึ่งต้องรักษาใบอนุญาตของแต่ละชิ้นเช่นกัน ไม่ได้อยู่ใต้ License ของน้ำหนักโมเดลโดยอัตโนมัติ

การติดตั้งด้วยการเลือกไฟล์ `.vwmodel v4` ครั้งเดียวเป็นการยอมรับเงื่อนไขและอนุญาตให้โปรแกรมเรียก Worker บนเครื่องของผู้ใช้ตามการออกแบบ v4 ไม่ต้องตรวจสอบ License Server

## ยืนยันเทียบ Release ที่เคยเผยแพร่

ตรวจจากไฟล์จริงในเครื่อง:

- V2 จำนวน 8 ไฟล์ใน `dist/ModelPackagesV2/` เทียบ SHA-256 และขนาด **ทั้ง ZIP** กับ GitHub Release `v0.10.3` ครบทั้ง 8 ไฟล์
- V3 จำนวน 5 ไฟล์ใน `dist/ModelPackagesV3/` เทียบ SHA-256 และขนาด **ทั้ง ZIP** กับ GitHub Release `v0.11.0` ครบทั้ง 5 ไฟล์
- เทียบ `manifest.files[].sha256` ของน้ำหนักโมเดล (ONNX, PT, PTH, NPY, BIN, Safetensors) โดยลบ prefix `assets/` ของ v4 ออก เพื่อเทียบไบต์ของไฟล์เดิมโดยตรง
- **ทุกโมเดลมีน้ำหนักเหมือน V2 ที่เคยเผยแพร่ครบถ้วน** และ 5 โมเดลที่มีใน V3 ก็เหมือน V3 ด้วย

| โมเดล | น้ำหนักเหมือน V2 | น้ำหนักเหมือน V3 | น้ำหนักโมเดล (ไฟล์) | Wheel ออฟไลน์ใน V4 |
| --- | --- | --- | ---: | ---: |
| MakHam Paradee | ใช่ | ใช่ | 1 | 26 |
| FastThaiG2P Thai Som | ใช่ | ใช่ | 2 | 26 |
| Melo Chinese ONNX | ใช่ | ใช่ | 1 | 3 |
| Supertonic 3 Multilingual INT8 | ใช่ | ใช่ | 6 | 3 |
| Kokoro Multilingual INT8 | ใช่ | ไม่มีใน Release V3 | 2 | 31 |
| Vachana Thai 4 Voices | ใช่ | ไม่มีใน Release V3 | 4 | 14 |
| Wayu Paxa Edge NC | ใช่ | ไม่มีใน Release V3 | 13 | 106 |
| M2M100 418M (Translation) | ใช่ | ใช่ | 1 | 25 |

ไฟล์เก็บผลเปรียบเทียบฉบับเต็ม: `dist/ModelPackagesV4-QA/RELEASE-PROVENANCE-v2-v3-to-v4.json` (ไม่อัปโหลดลง GitHub) ส่วนรายงานสรุปสำหรับอ้างอิงใน Git คือ [v4_weight_continuity_summary.json](v4_weight_continuity_summary.json)

**ผลการเทียบนี้เป็นหลักฐานว่าตัวโมเดลไม่ได้เปลี่ยน** และสามารถใช้ประวัติเอกสารสิทธิ์น้ำหนักโมเดลจากรอบ V2/V3 ต่อได้ ไม่ได้หมายความว่าการเคยเผยแพร่ครั้งก่อนเป็นใบอนุญาตทางกฎหมายฉบับใหม่

## แยก License ของน้ำหนักโมเดลจากสภาพแวดล้อม

| โมเดล | License ของน้ำหนักโมเดลตามต้นทาง | ประเด็นใหม่ของ V4 ที่ต้องจัดเอกสารให้ครบ |
| --- | --- | --- |
| MakHam Paradee | Apache-2.0; ชุดข้อมูลที่เกี่ยวข้อง CC BY 4.0 | `flatbuffers` ไม่มี License Text ภายใน Wheel; ต้องแนบ Notice/อ้างอิงต้นทาง |
| FastThaiG2P Thai Som | สิทธิ์ของน้ำหนัก/ชุดข้อมูลจากต้นทางตามเอกสารที่เคยแนบ | `flatbuffers` ไม่มี License Text ภายใน Wheel; ทบทวนการอ้างสิทธิ์น้ำหนัก/ข้อมูลเสียงของ Som |
| Melo Chinese ONNX | MIT | `sherpa-onnx-core` Wheel ไม่มี License Text ภายใน ต้องแนบข้อความสิทธิ์ของ Native Runtime |
| Supertonic 3 | **OpenRAIL-M** | `sherpa-onnx-core` Wheel ไม่มี License Text ภายใน; ต้องรักษาข้อจำกัดการใช้ตาม OpenRAIL-M |
| Kokoro 82M | Apache-2.0 | `phonemizer` GPLv3+, Native eSpeak-NG, `espeakng-loader` และเอกสาร/source obligations |
| Vachana | MIT ตาม HF Model Card ของโมเดล | `vachanatts 0.0.7` Wheel ยังไม่ระบุ License ชัดเจน ต้องตรวจสิทธิ์โค้ด Wheel แยกจากโมเดล |
| Wayu Paxa Edge NC | **CC BY-NC 4.0**; แจกจ่ายโดยรักษา Attribution, เงื่อนไข NC และ Acceptable Use | 106 Wheel รวม `phonemizer-fork`, `gensim`, `num2words`, eSpeak-NG และ Native Runtime ต้องแนบ Notices/Source obligations |
| M2M100 418M | MIT ตาม HF Model Card | `sentencepiece`, `tokenizers` Wheel/Native Notices และ Runtime ใหญ่ |

**Wayu ไม่ใช่โมเดลต้องห้ามของโครงการ** เพียงต้องกำกับว่า NonCommercial และปฏิบัติตามข้อจำกัดเดิม ห้ามโฆษณาว่าใช้งานเชิงพาณิชย์ได้โดยเสรี ขณะเดียวกัน GPL/LGPL **ไม่ได้แปลว่าห้ามแจกจ่ายหรือห้ามใช้เชิงพาณิชย์** แต่มีข้อกำหนดการแจก Source/Notices ที่ต่างกันตามชิ้นงาน

## วิธีใช้หลักฐานเดิมเพื่อลดงานซ้ำ

1. นำ License/Attribution/Model Card ของไฟล์น้ำหนักที่มี SHA-256 ตรงกับ V2/V3 มาใช้อ้างอิงต่อ
2. เก็บสำเนาต้นฉบับที่ Commit/Revision คงที่จากผู้เผยแพร่ใน `cache/v4-rights-evidence/upstream/` และเอกสาร Metadata/License ของ Wheel ใน `cache/v4-rights-evidence/wheel-docs/`
3. ทำ THIRD_PARTY_NOTICES **รายแพ็กเกจ V4** ให้แยกเอกสาร License ของโมเดลกับ Dependency, รวมถึง Source/Source Offer ที่ใบอนุญาตกำหนด
4. ก่อนเผยแพร่แพ็กเกจใด ตรวจว่าไฟล์ใหม่ทุกไฟล์มีสิทธิ์แจกจ่ายที่ยืนยันได้ ไม่จำเป็นต้องย้อนประเมินสิทธิ์น้ำหนักที่ไม่เปลี่ยนซ้ำทั้งหมด
5. แจกแพ็กเกจแยกจาก Core (ไม่ต้องรวมทุกโมเดลไว้ใน Portable) โดยระบุ License เดิมอย่างชัดเจน รวมถึง NonCommercial ที่มี

การเปรียบเทียบเทคนิคเสร็จแล้ว แต่ **ยังไม่มีการออก GitHub Release ของแพ็กเกจ V4 ทั้ง 8 ตัวในขั้นตอนนี้** ระหว่างจัดชุดเอกสารของ Dependencies ตามสิทธิ์ต้นทาง
