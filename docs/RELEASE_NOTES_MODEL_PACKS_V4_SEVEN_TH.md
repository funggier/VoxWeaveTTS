# VoxWeaveTTS — Offline Model Packs V4 (7 Models)

**Tag:** `v0.12.1-modelpacks-v4`
**โปรแกรมหลักที่แนะนำ:** [VoxWeaveTTS Core v0.12.2 Windows Portable](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.2) — **จำเป็นสำหรับ Kokoro และ Wayu** (Core v0.12.1 จะปฏิเสธไฟล์ Source `.tar.gz` ในแพ็กเกจสองตัวนี้)
**รูปแบบ:** `.vwmodel` **V4 เท่านั้น** · Windows x64 / Python 3.11 · ติดตั้งจากไฟล์เดียวแบบออฟไลน์ · ไม่ใช้ License Server

## โมเดลที่เผยแพร่

| โมเดล | การใช้งาน | License หลักที่ต้องคงไว้ |
| --- | --- | --- |
| MakHam Paradee | อ่านเสียงภาษาไทย | **Apache-2.0**; ระบุแหล่งข้อมูลฝึก CC BY 4.0 |
| FastThaiG2P Thai Som | อ่านภาษาไทย | **Apache-2.0** ตามแพ็กเกจโมเดลต้นทาง |
| Melo Chinese ONNX | อ่านภาษาจีน | **MIT** สำหรับโมเดล; sherpa-onnx Apache-2.0 |
| Supertonic 3 Multilingual INT8 | อ่านเสียงหลายภาษา | **OpenRAIL-M** — มีข้อจำกัดการใช้งานและแจกต่อ |
| Kokoro Multilingual INT8 | อ่านเสียงหลายภาษา | **Apache-2.0** สำหรับน้ำหนัก; GPLv3+ ของ G2P/phonemizer/eSpeak NG ยังคงใช้ |
| Wayu Paxa Edge NC | อ่านเสียงไทย/อังกฤษ | **CC BY-NC 4.0 — ห้ามใช้เชิงพาณิชย์** สำหรับน้ำหนักเสียง; เงื่อนไข Acceptable Use ของ Wayu ยังใช้ |
| M2M100 418M | แปลภาษาแบบ Local | **MIT** ของ Model Repository; Runtime ใช้สิทธิ์ต้นฉบับแยก |

**ไม่เผยแพร่:** `Vachana / vachanatts` — เก็บแพ็กเกจและซอร์สอยู่เฉพาะในเครื่องพัฒนา เพราะยังไม่พบ License ที่ให้สิทธิ์แจกโค้ด `vachanatts 0.0.7` อย่างชัดเจน

## วิธีใช้

1. ดาวน์โหลด **Core v0.12.2 Portable** จากลิงก์ข้างบนและแตก ZIP ในโฟลเดอร์ที่ต้องการ (หากใช้ Kokoro หรือ Wayu ต้องอัปเดตจาก Core v0.12.1)
2. ดาวน์โหลดไฟล์ `.vwmodel` **แยกตามโมเดล** ที่ต้องการจาก Release นี้ (ไม่ต้องโหลดทั้งหมด)
3. เปิด VoxWeaveTTS เข้าเมนูจัดการโมเดล แล้วเลือกติดตั้งจากไฟล์ `.vwmodel` ที่ดาวน์โหลดมา
4. อ่าน/ยอมรับข้อความแจ้งสิทธิ์ของแต่ละโมเดล การติดตั้ง Runtime และ Dependencies เกิดจากไฟล์แพ็กเกจในเครื่อง ไม่ต้องเชื่อมต่อแหล่งดาวน์โหลดหรือเซิร์ฟเวอร์ License
5. ใช้โมเดลที่ติดตั้งแล้วในโหมดอ่าน/แปลที่รองรับ **สามารถถอนแล้วติดตั้งใหม่ได้** โดยไม่ต้องใช้กระบวนการซ่อม

โปรแกรมหลัก `v0.12.2` ไม่ได้บรรจุโมเดลเหล่านี้ใน ZIP และใช้ไฟล์โมเดล V4 โดยตรง ไม่รองรับ V2/V3 ในโปรแกรมหลักนี้ ไฟล์ `.vwmodel` ทั้ง 7 ตัวไม่เปลี่ยนจาก Release เดิม

## ขอบเขตการใช้และเอกสารสิทธิ์

**ไฟล์แต่ละโมเดลคงน้ำหนัก, Worker, Runtime Wheel และ License/Attribution ของผู้เผยแพร่ต้นทางโดยไม่มีการเปลี่ยนเนื้อหา** เอกสารสิทธิ์ที่เพิ่มอยู่ภายใน `assets/legal/` ของแพ็กเกจ ประกอบด้วยสำเนา License/Notice จาก Wheel จริงและดัชนี SHA-256 สำหรับตรวจที่มา รวมถึง:

- Microsoft ONNX Runtime v1.28.2 หรือ v1.31.1 พร้อม MIT License และ `ThirdPartyNotices.txt` ตรงตามรุ่น DLL
- sherpa-onnx Apache-2.0, Flatbuffers Apache-2.0, SentencePiece Apache-2.0 และ tokenizers Apache-2.0 (เมื่อมีในแพ็กเกจ)
- Kokoro/Wayu: eSpeak NG 1.52.0 GPL Source และ Build Script/Workflow ของ `espeakng-loader 0.2.4`; Python GPL/LGPL Source Distribution ของ `phonemizer`, `phonemizer-fork`, `gensim`, `num2words` ตามที่บรรจุจริง
- License ของน้ำหนัก Supertonic OpenRAIL-M, Wayu CC BY-NC 4.0 และเงื่อนไข Acceptable Use ที่เกี่ยวข้อง **ต้องไม่ถูกลบหรือแทนที่ด้วย MIT ของ Core**

**ไม่ใช่ใบอนุญาตใหม่:** การเผยแพร่ผ่านโครงการ VoxWeaveTTS ภายใต้ MIT **ไม่ได้แปลงโมเดลหรือไลบรารีบุคคลที่สามให้เป็น MIT** ผู้ใช้และผู้แจกจ่ายต่อจะต้องทำตาม License ของแต่ละส่วน รวมทั้ง Source/Notice/Copyright และเงื่อนไขการใช้ที่แนบไว้ แม้จะใช้งานแบบไม่แสวงหากำไรก็ตาม

**หมายเหตุการตรวจ:** แฟ้ม `provenance.json` บางไฟล์มี `public_release_authorized:false` ซึ่งเป็นสถานะของ **ชุดหลักฐาน QA ขณะสร้าง** ไม่ใช่ข้อความจากผู้ทรงสิทธิ์ต้นทางที่ห้ามการใช้งานโมเดล; การเผยแพร่ชุดนี้อยู่ภายใต้ License ต้นฉบับตามรายการข้างต้น การตรวจด้านเทคนิคไม่ถือเป็นคำรับรองทางกฎหมาย

## ความถูกต้องของไฟล์และรายการดาวน์โหลด

- ชื่อไฟล์สาธารณะรูปแบบ `VoxWeaveTTS-<model>-<model-version>-format-v4.vwmodel` (ไม่มีคำว่า QA)
- แนบ `SHA256SUMS-v0.12.1-modelpacks-v4.txt` ใน Release นี้ ใช้ตรวจสอบความถูกต้องของทั้ง 7 ไฟล์
- ผล QA: **7 แพ็กเกจ, 220 Runtime Wheels ตามรายการในแพ็กเกจ, น้ำหนักและไฟล์ Worker ไม่เปลี่ยนจากรุ่น QA ต้นทาง**; ตรวจ SHA-256 และเอกสารเพิ่มเติมตามรุ่น Dependency
- ไม่มี Vachana หรือโค้ด `vachanatts` ในไฟล์เผยแพร่ทั้งเจ็ด

### วิธีตรวจ SHA-256 บน Windows

หลังดาวน์โหลด เปิด PowerShell ในโฟลเดอร์ที่มีไฟล์โมเดล แล้วใช้:

```powershell
Get-FileHash -Algorithm SHA256 .\VoxWeaveTTS-ชื่อโมเดล-format-v4.vwmodel
```

นำค่า SHA256 ไปเทียบกับรายการของชื่อไฟล์นั้นใน `SHA256SUMS-v0.12.1-modelpacks-v4.txt`

Source Project: https://github.com/funggier/VoxWeaveTTS

## การเปลี่ยนแปลงเมื่อเทียบกับ V2/V3

- โมเดลยังเป็นน้ำหนักเดิมที่ได้รับการเผยแพร่ไปแล้ว; V4 เพิ่มสภาพแวดล้อมและ Dependencies สำหรับติดตั้งและใช้งานแยกได้ในเครื่อง
- เพิ่มเอกสารสิทธิ์และซอร์สที่จำเป็นสำหรับไลบรารีที่แจกเป็น Binary
- ไม่รวมโมเดลเป็นส่วนหนึ่งของ Core; ไม่เปลี่ยนเงื่อนไขต้นทางให้เป็นสิทธิ์เชิงพาณิชย์ใหม่
