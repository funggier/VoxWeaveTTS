# VoxWeaveTTS V4 — หลักฐานไบนารีและเอกสารต้นทาง (ตรวจต่อจาก v0.12.1)

วันที่ 20 พฤศจิกายน 2026 · **Technical QA เท่านั้น / ไม่ใช่การรับรองสิทธิ์แจกจ่าย**

## ขอบเขต

V4 นำโมเดล/น้ำหนักจาก V2/V3 มาใส่ในไฟล์พร้อม Worker และ Python Wheels สำหรับติดตั้งออฟไลน์ โดย **คง License เดิมของน้ำหนักทุกโมเดล** ไว้ตามจริง ไม่เปลี่ยนสิทธิ์เป็น MIT/Apache โดยพลการ และไม่ตัด Wayu ทิ้งเพียงเพราะ CC BY-NC 4.0

การตรวจนี้แยก (1) สิทธิ์น้ำหนัก/ข้อมูลฝึก (2) สิทธิ์โค้ด Worker (3) สิทธิ์ Wheel และ DLL/Native ที่แนบใหม่ (4) ข้อกำหนด Source/Notice สำหรับการแจกไบนารี การใช้ส่วนตัวกับการแจกไฟล์ให้ผู้อื่นมีข้อกำหนดไม่เหมือนกัน

## ตรวจลงถึง SHA-256 ของ Native Files ภายใน Wheel

สคริปต์ `scripts/audit_v4_wheel_licenses.py` ตรวจ SHA-256 ของไฟล์ Wheel จาก Manifest ก่อนเปิดอ่าน และคำนวณ SHA-256 ของ .dll/.pyd/.exe/.so/.dylib ภายใน Wheel ทุกไฟล์จริง แยกไฟล์ที่อยู่คนละพาธแต่เนื้อหาเหมือนกัน

สรุปจาก `cache/v4-qa-candidates/rights-wheel-audit-native-20261120.json`:

| โมเดล | Wheel | Wheel ที่มี Native | ไฟล์ Native (รวมพาธซ้ำ) |
| --- | ---: | ---: | ---: |
| MakHam Paradee | 26 | 7 | 29 |
| FastThaiG2P Thai Som | 26 | 7 | 29 |
| Melo Chinese ONNX | 3 | 3 | 28 |
| Supertonic 3 | 3 | 3 | 28 |
| Kokoro Multilingual | 31 | 9 | 34 |
| Vachana Thai 4 Voices | 14 | 4 | 26 |
| Wayu Paxa Edge NC | 106 | 28 | 366 |
| M2M100 418M | 25 | 9 | 44 |

**รวมทั้งหมด:** 234 Wheel ตามแพ็กเกจ, **137 Wheel SHA ไม่ซ้ำ** และ **400 Native Payload SHA ไม่ซ้ำ** ระหว่างแพ็กเกจ แพ็กเกจหนึ่งอาจมีสำเนา DLL เดียวกันหลายพาธ

## Melo และ Supertonic: Sherpa-ONNX / Microsoft ONNX Runtime

ใน `sherpa_onnx_core-2.0.1` ที่บรรจุจริง `sherpa_onnx/lib/onnxruntime.dll` มี Windows FileVersion **1.28.2** และ SHA-256:

`7f66f939a881baf4f46a2216496798edf4a1429878b646d12674aa62f27d8a25`

สำเนา DLL อีกพาธภายใน Wheel มี SHA เดียวกัน เอกสารทางการจาก Microsoft ที่เก็บไว้แบบไม่แก้ไขเนื้อหา:

- `LICENSE` MIT, 1,073 ไบต์, SHA-256 `2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c`
- `ThirdPartyNotices.txt`, 325,054 ไบต์, SHA-256 `0e07b95f3a8d6230037707c5c4a2b554d12c4cb67369669ac255635528ffcee2`
- URL: `https://cdn.jsdelivr.net/gh/microsoft/onnxruntime@v1.28.2/LICENSE` และ `https://cdn.jsdelivr.net/gh/microsoft/onnxruntime@v1.28.2/ThirdPartyNotices.txt`
- **ข้อจำกัดแหล่งอ้างอิง:** URL ใช้ GitHub tag `v1.28.2` ผ่าน jsDelivr โดยตรวจ SHA ของเอกสาร ไม่ได้ยืนยัน Git commit ที่ immutable ด้วย API ในรอบนี้

สคริปต์ `scripts/archive_v4_sherpa_native_notices.py` บันทึกไว้ใน `cache/v4-rights-evidence/runtime-sources/onnxruntime-1.28.2/` และ `scripts/repackage_v4_with_legal_evidence.py` ประกอบสำเนา LICENSE, ThirdPartyNotices และ Provenance ลงใน QA แพ็กเกจ Melo/Supertonic อีกชุดที่ `dist/ModelPackagesV4-NativeNoticeQA/`

ตรวจด้วย `scripts/verify_v4_legal_packaging.py --repacked dist/ModelPackagesV4-NativeNoticeQA --models melo-chinese-onnx supertonic3-multilingual-int8 --require-native-notices` โดยเปรียบเทียบน้ำหนัก/Worker/Wheel ทุกไฟล์กับต้นฉบับ รวมทั้ง SHA ของ DLL และเอกสารต้นทาง

**ยังค้าง:** ต้องตรวจ Notice และสิทธิ์ของ native-linked components *ทั้งหมด* ใน sherpa DLL และสิทธิ์ model conversion ก่อนเผยแพร่; เอกสาร ONNX Runtime เพียงส่วนเดียวไม่ปลดล็อกการแจกแพ็กเกจทั้งตัว

## Kokoro และ Wayu: eSpeak NG / GPLv3+

ใน `espeakng_loader-0.2.4` ที่บรรจุจริง `espeakng_loader/espeak-ng.dll` SHA-256:

`646d387acbc7ac2aa45e3625aa00a6835ae5d446ff8b0748298c3900b4dde258`

ตรงกันทั้งสองแพ็กเกจ Wheel นี้ไม่ได้ประกาศ License ใน Metadata ที่ตรวจพบ ต้องแยกสองโครงการ:

- **espeakng-loader (ตัวโหลด)**: upstream source MIT License, commit `0ddc87adf77e5850d7eeb542ac8a87d421b64daa`
- **eSpeak NG (DLL ต้นทาง)**: GPLv3+; upstream workflow ของ loader ข้างต้นระบุ `git clone --single-branch --depth 1 -b 1.52.0` และใช้ `build.sh` สร้าง Windows Native Library

เก็บไฟล์ต้นฉบับจาก `https://codeload.github.com/espeak-ng/espeak-ng/tar.gz/refs/tags/1.52.0` ทั้งชุด ขนาด 17,739,803 ไบต์, SHA-256:

`bb4338102ff3b49a81423da8a1a158b420124b055b60fa76cfb4b18677130a23`

ZIP ของซอร์สต้นทางใช้รูปแบบ `tar.gz`; ได้ตรวจว่ามี `COPYING` ซึ่งเป็น GNU GPLv3 พร้อมทั้งเก็บ `LICENSE`, `build.sh`, `.github/workflows/build.yml` จาก loader commit ต้นทางแบบไม่แก้เนื้อหา สคริปต์ `scripts/archive_v4_espeak_source.py` สร้างรายการแหล่งที่มาและ SHA ที่ `cache/v4-rights-evidence/runtime-sources/espeak-ng-1.52.0/INDEX.json`

สคริปต์ประกอบแพ็กเกจจะใส่ซอร์สต้นทางใน **พาธเดียวที่ระบบ V4 อนุญาต** `assets/legal/source/espeak-ng-1.52.0-source.tar.gz` พร้อมเอกสาร License/Build/Provenance ลงชุด `dist/ModelPackagesV4-GPLSourceQA/`; ไม่แตะ Worker/น้ำหนัก/Runtime Wheel เดิม

**ยังค้าง:** การระบุ tag ใน Workflow ไม่เท่ากับการพิสูจน์ว่า DLL ที่ถูกแจกนั้นสร้างจากซอร์สเดียวกันแบบตรงไบนารี ต้องตรวจ Complete Corresponding Source, build configuration และส่วนประกอบอื่นของ GPL พร้อมเงื่อนไขของ `phonemizer`, Wayu wheels จำนวนมาก และ Wayu Acceptable Use ด้วย *Wayu CC BY-NC ไม่ใช่เหตุให้ห้ามแจกแบบไม่ใช่เชิงพาณิชย์โดยตัวมันเอง*

## ONNX Runtime 1.31.1 / Vachana PyPI Source QA รอบต่อเนื่อง

ดู [V4_RUNTIME_SOURCE_PROVENANCE_2026-11-20_TH.md](V4_RUNTIME_SOURCE_PROVENANCE_2026-11-20_TH.md) สำหรับเอกสาร ONNX Runtime 1.31.1 ที่ตรงกับ DLL ใน MakHam/FastThaiG2P/Kokoro/Vachana และการตรวจ Source Distribution ของ `vachanatts 0.0.7` รวมถึงโค้ด namespace เพิ่ม 9 ไฟล์ที่ยังขาดการยืนยันสิทธิ์

## สถานะและขั้นตอนที่ต้องเหลือ

| ชุด QA | สถานะเทคนิค | การเผยแพร่ |
| --- | --- | --- |
| `ModelPackagesV4-NoticeQA` (8 โมเดล) | น้ำหนัก/Wheel ตรงต้นฉบับ พร้อม Wheel notices | **ยังไม่แจก** |
| `ModelPackagesV4-NativeNoticeQA` (Melo, Supertonic) | เพิ่มเอกสาร ONNX Runtime ตามรุ่น DLL | **ยังไม่แจก** |
| `ModelPackagesV4-GPLSourceQA` (Kokoro, Wayu) | เพิ่มซอร์ส GPL และ Build ต้นฉบับ | **ยังไม่แจก** |
| Vachana / M2M100 / MakHam / FastThaiG2P | เดิมมีชุด NoticeQA, ต้องตรวจสิทธิ์และ Native Notices ต่อ | **ยังไม่แจก** |

ช่องว่างหลักที่ต้องปิดเพิ่ม: `vachanatts 0.0.7` License ของโค้ด Wheel, สิทธิ์และ Notices ของ Native/Transitive Dependencies แต่ละโมเดล, ข้อกำหนด GPL/LGPL สำหรับ Corresponding Source, และ model/data provenance ที่ยังไม่ได้พิสูจน์ครบ เอกสารชุดนี้เป็นหลักฐานทางเทคนิคสำหรับตรวจสิทธิ์ **ไม่ใช่คำวินิจฉัยทางกฎหมาย** และไม่เปลี่ยน `public_release_authorized:false`

Core รุ่นสาธารณะยังเป็น `v0.12.1` ไม่ควรติดป้ายไฟล์ QA เป็น Public Release จนการตรวจการแจกไฟล์ครบทุกองค์ประกอบที่บรรจุจริง
