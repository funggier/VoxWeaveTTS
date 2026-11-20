# การเทียบ License หลักของ VoxWeaveTTS และ Model Packages V4

ตรวจวันที่ 20 พฤศจิกายน 2026 — **ใช้หลัก "ถ้าสิทธิ์หลักไม่ขัดกัน ให้รักษาสิทธิ์เดิมแล้วใช้ได้ตามเงื่อนไข"** ไม่บังคับแปลง License ของบุคคลที่สามเป็น MIT ไม่กำหนดว่าต้องใช้งานเชิงพาณิชย์ได้ และไม่ถือว่า Wheel ที่ไม่มีช่อง `License` ใน Metadata เป็นความขัดแย้งโดยอัตโนมัติ

## โครงสร้างสิทธิ์ที่ใช้จริง

- **VoxWeaveTTS Core:** MIT — `LICENSE` ของโปรเจกต์ ใช้กับโค้ดของโครงการเอง
- **น้ำหนักโมเดล / ข้อมูลฝึก:** ตาม License ของผู้เผยแพร่ต้นทางแต่ละชุด ไม่ใช่ MIT เพียงเพราะถูกเปิดใช้งานผ่าน VoxWeaveTTS
- **Worker / Adapter:** แยกโค้ดของโครงการออกจากโค้ด Third Party และคง Copyright/License ของเจ้าของเดิม
- **Python Wheels และ DLL:** ใช้ License หลักของโปรเจกต์/ซอร์สที่ผลิต Wheel และข้อกำหนด Third-Party Notices/Corresponding Source ของชิ้นส่วนที่ฝังภายใน
- **วิธีแจก:** `.vwmodel v4` ติดตั้งแบบออฟไลน์ เป็น Container ที่เก็บ Component ต่าง License ได้ ผู้รับสิทธิ์ของแต่ละ Component ยังคงตามต้นทาง; การแยก Container/Process ไม่พิสูจน์โดยตัวมันเองว่าโค้ดที่เชื่อมกันไม่เป็น derivative work

**กฎการตัดสิน:** "ไม่พบข้อขัดแย้งโดยอัตโนมัติ" **ไม่เท่ากับ** "ได้รับอนุญาตให้แจกทุกไฟล์แล้ว" ต้องตรวจสิทธิ์สำหรับการแจกไฟล์ที่อยู่ในแพ็กเกจจริงครบ ทั้งโค้ด Native และข้อกำหนด Attribution/Source เมื่อเกี่ยวข้อง

## ตารางตรวจ License หลักและความเข้ากันได้

| Model Package | License หลักของน้ำหนัก / ต้นทาง | เทียบกับ Core MIT | เงื่อนไขหรือช่องว่าง |
| --- | --- | --- | --- |
| MakHam Paradee | Apache-2.0; Dataset CC BY 4.0 | ไม่มีข้อขัดแย้งโดยตรงสำหรับการแยก Component | ให้เครดิตข้อมูลฝึกตามต้นฉบับ และเก็บ Runtime Notices |
| FastThaiG2P Thai Som | Apache-2.0 ตาม Package Declaration | ไม่มีข้อขัดแย้งโดยตรง | ตรวจข้อกำหนดของเสียง/น้ำหนัก/ข้อมูลฝึกเฉพาะ และ Runtime |
| Melo Chinese ONNX | MIT; sherpa-onnx Apache-2.0; ONNX Runtime MIT | รองรับการแจกแบบคงสิทธิ์แยก | ตรวจ Provenance ของ ONNX Conversion และเอกสาร Native Component |
| Supertonic 3 | OpenRAIL-M; Runtime Apache-2.0/MIT | ไม่ต้องเปลี่ยนเป็น MIT | ต้องคง Restriction, Attribution, Redistribution Terms ของ OpenRAIL-M |
| Kokoro Multilingual | Apache-2.0 (น้ำหนัก); phonemizer GPL-3.0-or-later / eSpeak NG GPL-3.0-or-later | GPLv3 ไม่ขัด MIT โดยตัวมันเอง | ปฏิบัติตาม Source/Notices และประเมินความสัมพันธ์ของงานที่เชื่อมกัน ขณะนี้เก็บ eSpeak Source ใน QA แล้ว |
| Vachana Four Voices | MIT (Model Card) | **ยังสรุปสิทธิ์โค้ดไม่ได้** | `vachanatts 0.0.7` และ repo VYNCX/VachanaTTS2 ยังไม่พบ License หลักของโค้ดที่ระบุสิทธิ์แจกต่อ |
| Wayu Paxa Edge NC | CC BY-NC 4.0 (น้ำหนัก); Inference Apache-2.0 | **ไม่ใช่ข้อห้ามแจกแบบ NonCommercial โดยอัตโนมัติ** | ห้ามใช้เชิงพาณิชย์ตามเงื่อนไขน้ำหนัก; คง Acceptable Use และประเมินความสัมพันธ์กับ GPL Wheel/Runtime |
| M2M100 418M | MIT (Model Card) | ไม่มีข้อขัดแย้งโดยตรง | ต้องคง Notices ของ Torch, Transformers และ Native Runtime |

**ข้อแตกต่างสำคัญ:** การใส่ Component ภายใต้ GPL, OpenRAIL หรือ CC BY-NC ในแพ็กเกจแยก ไม่ได้ทำให้โปรเจกต์ Core MIT เปลี่ยน License เองโดยอัตโนมัติ แต่ข้อผูกพันอาจขยายถึงงานที่เป็น Derivative/Combined Work ตามลักษณะการเชื่อมจริง จึงไม่สามารถสรุปความเข้ากันได้จากชื่อไฟล์ ZIP อย่างเดียว

## ตรวจ Primary License จากผู้เผยแพร่ตัวจริง

**Vachana:**

- [Hugging Face Model Card](https://huggingface.co/VIZINTZOR/VachanaTTS) ระบุ MIT สำหรับ Model Repository
- [GitHub VYNCX/VachanaTTS2](https://github.com/VYNCX/VachanaTTS2) และ [VYNCX/VachanaTTS](https://github.com/VYNCX/VachanaTTS) — GitHub Repository API คืน `license: null` และไม่พบ `LICENSE` ที่ root ของ VachanaTTS2 ในการตรวจครั้งนี้
- [PyPI vachanatts 0.0.7](https://pypi.org/project/vachanatts/0.0.7/) — Wheel และ sdist ไม่มี `License`/`License-Expression`; สคริปต์ตรวจต้นฉบับแยก `scripts/audit_v4_vachanatts_pypi_provenance.py` พบ 16 ซอร์สไฟล์ที่ตรงกัน และ `vachanatts1` อีก 9 ไฟล์ใน Wheel ซึ่งไม่มีใน sdist
- **ดังนั้น:** ไม่ใช่พบ License ขัดแย้ง แต่ยังหาใบอนุญาตให้แจก **โค้ด Wheel** ไม่พบ ไม่สามารถอ้าง MIT ของ Weight มาแทนใบอนุญาตโค้ดได้

**GPL:**

- [eSpeak NG](https://github.com/espeak-ng/espeak-ng) ระบุ GPLv3-or-later; [phonemizer](https://pypi.org/project/phonemizer/) ก็ระบุ GPLv3-or-later; ทั้งสองไม่ได้ห้ามการแจกจ่ายหรือการค้าในตัวมันเอง
- [espeakng-loader](https://github.com/thewh1teagle/espeakng-loader) มีโค้ดตัวโหลด MIT แต่ DLL ที่ใส่ใน Wheel เป็น eSpeak NG GPL ตาม License ต้นทางคนละตัว
- ได้คัดลอก Source และ Build Workflow ของ eSpeak NG 1.52.0, MIT/Notices ของ ONNX Runtime 1.28.2/1.31.1 ไว้ใน **QA ของแต่ละแพ็กเกจที่เกี่ยวข้อง** (หลักฐาน SHA ดูเอกสารในลิงก์ด้านล่าง)

**Wayu:** [Model Card](https://huggingface.co/wayu-ai/wayu-paxa-tts-edge) แสดง CC BY-NC 4.0 ไม่ได้ขัดกับเจตนาแจกแบบไม่ใช่เชิงพาณิชย์โดยตัวมันเอง แต่ **ต้องยอมรับ NC** และรักษา License/เงื่อนไขแยกของ Inference/Native Code

## ผลต่อการพัฒนาและ Release

1. ปรับ `provider_rights.py` ให้แสดง `primary_license_comparison` **แยก** จาก `publication_state` (อย่างหลังยังต้องการหลักฐาน Redistributor Conditions จริง)
2. สถานะ Kokoro และ Wayu ในทะเบียนตรวจ V4 เปลี่ยนจาก `hold` เป็น `review-required` เพราะ **ไม่พบใบอนุญาตหลักที่ห้ามรูปแบบ NonCommercial อย่างอัตโนมัติ**; ยังต้องตรวจ Source/Notices ที่บรรจุจริงต่อ
3. Vachana คง `hold` **ไม่ใช่เพราะ MIT ขัดกับ Core** แต่เพราะยังไม่พบ License ที่ให้สิทธิ์แจก Wheel Code
4. **ผู้ใช้ยังติดตั้งแพ็กเกจที่ตรวจรูปแบบผ่านได้แบบออฟไลน์โดยไม่ต้องมี License Server**; ทะเบียนนี้ไม่ใช่ Installer Allowlist
5. ไม่เปลี่ยน `public_release_allowed` เป็น `true` จากการเห็นคำว่า MIT, GPL หรือ Apache อย่างเดียว และไม่เอา QA ที่มีข้อกำหนดค้างขึ้น Public Release โดยพลการ

ดูต่อ: [V4_RUNTIME_SOURCE_PROVENANCE_2026-11-20_TH.md](V4_RUNTIME_SOURCE_PROVENANCE_2026-11-20_TH.md), [V4_NATIVE_COMPONENT_EVIDENCE_2026-11-20_TH.md](V4_NATIVE_COMPONENT_EVIDENCE_2026-11-20_TH.md), [V4_RIGHTS_REVIEW_TH.md](V4_RIGHTS_REVIEW_TH.md)

เอกสารนี้เป็น Technical/License Compatibility Review ไม่ใช่คำวินิจฉัยทางกฎหมาย
