# VoxWeaveTTS — การตรวจสิทธิ์แพ็กเกจ Universal v4 (รอบเริ่มต้น)

วันที่ตรวจ: 20 พฤศจิกายน 2026
สถานะ: **QA ONLY / ยังไม่อนุมัติ Public Redistribution ทั้ง 8 แพ็กเกจ**

## สิ่งที่ยืนยันได้ และสิ่งที่ยังยืนยันไม่ได้

แพ็กเกจ `.vwmodel v4` ทั้ง 8 ตัวผ่านการตรวจข้อมูล Manifest, SHA-256 และการติดตั้งออฟไลน์/ประมวลผลจริงบน Windows Portable v4-only แล้ว แต่ **การทำงานได้ไม่ใช่หลักฐานว่ามีสิทธิ์แจกจ่าย** น้ำหนักโมเดล โปรแกรมอนุมาน หรือ Wheel ที่บรรจุมาด้วย

ผู้ใช้เลือกไฟล์ติดตั้งเองถือเป็นการอนุญาตให้ **โปรแกรมเรียกใช้ Worker บนเครื่องของผู้ใช้** ตามการออกแบบ v4 (ไม่มีการเช็ค License Server) แต่ **ไม่ได้ให้สิทธิ์ทางลิขสิทธิ์แก่ผู้พัฒนา** ที่จะอัปโหลดแพ็กเกจของบุคคลที่สามขึ้น GitHub Release

การตรวจนี้เป็นข้อมูลต้นทางและข้อจำกัดทางเทคนิค ไม่ใช่คำวินิจฉัยทางกฎหมาย และไม่อนุมัติสิทธิ์เชิงพาณิชย์ให้โมเดลใดโดยอัตโนมัติ

## สิทธิ์ที่ต้นทางประกาศและประเด็นค้าง

| แพ็กเกจ v4 | License ของโมเดลที่ต้นทางประกาศ | สถานะเผยแพร่ | สิ่งที่ต้องตรวจ |
| --- | --- | --- | --- |
| MakHam Paradee | Apache-2.0 | REVIEW | ที่มาของโมเดล/Paradee, dataset CC BY 4.0 และ Attribution; Wheel ของ PyThaiTTS |
| FastThaiG2P Thai Som | Apache-2.0 ตามแพ็กเกจ/ระบบ PyThaiTTS | REVIEW | สิทธิ์น้ำหนักโมเดลและ dataset เฉพาะ, Attribution, Wheel 26 ตัว |
| Melo Chinese ONNX | MIT | REVIEW | สิทธิ์ไฟล์ ONNX ที่ถูกแปลงโดย sherpa-onnx และ Native Wheel/Notices |
| Supertonic 3 | **OpenRAIL-M** | REVIEW | ข้อจำกัดการใช้งานตาม Model License, เงื่อนไขการแจกต่อและ Attribution, ONNX conversion |
| Kokoro Multilingual | Apache-2.0 (weights) | **HOLD** | `phonemizer` GPL-3.0-or-later; `espeakng-loader` Native Libraries; ข้อกำหนดแจก Source/Notices และ G2P |
| Vachana Thai 4 Voices | MIT (Hugging Face model card) | **HOLD** | `vachanatts 0.0.7` Wheel ยังไม่มี License Declaration/Text เพียงพอ; ต้องไม่ถือว่า MIT ของ weights ครอบคลุมโค้ดทุกชุด |
| Wayu Paxa Edge NC | **CC BY-NC 4.0** | **HOLD** | **ใช้เชิงพาณิชย์ไม่ได้ตามสิทธิ์น้ำหนักโมเดลที่ประกาศ**; Acceptable Use และ Dependencies/Native Wheel 106 ตัว |
| M2M100 418M | MIT (Hugging Face model card) | REVIEW | สิทธิ์ dataset/โมเดล และ Transformer/Torch/Safetensors Wheels 25 ตัว |

คำว่า REVIEW หมายถึง **ยังไม่อนุมัติให้แจกจ่าย** เช่นเดียวกับ HOLD แต่เป็นสถานะที่ยังไม่ได้พบข้อขัดข้องเฉพาะเจาะจงเท่า HOLD

**ข้อสังเกต:** GPL ไม่ได้ห้ามการใช้งานเชิงพาณิชย์โดยอัตโนมัติ แต่การแจกจ่ายโปรแกรม/ไบนารี GPL อาจมีภาระหน้าที่เรื่อง License, Corresponding Source และการเชื่อมโยงโค้ดต่างหาก ต้องประเมินให้ตรงกับสิ่งที่บรรจุจริง

## ผลสแกน Wheel จากไฟล์จริง (รอบ 20 พฤศจิกายน 2026)

สแกน `*.whl` ภายในแพ็กเกจ QA ทั้ง 8 ตัวจาก ZIP โดยตรวจ SHA-256 เทียบ Manifest ทุก Wheel ก่อนอ่าน Metadata และไม่ได้รันโค้ดของ Wheel หรือเชื่อมต่อออนไลน์ ผลคือ **234 รายการ Wheel รวมตามแพ็กเกจ ซึ่งมี Wheel ไม่ซ้ำกัน 137 ตัว** และมี Wheel ที่บรรจุ Native Binary **40 ตัวที่ไม่ซ้ำกัน**

พบ Wheel ที่ **ไม่มี License Declaration ใน Metadata** 4 ชื่อ ได้แก่ `espeakng-loader 0.2.4` (ไม่มี License Text ที่สแกนพบ), `kokoro-onnx 0.6.0` (มี License Text แต่ไม่ระบุช่อง License), `sentencepiece 0.2.1` (ไม่มี License Text ที่สแกนพบ) และ `vachanatts 0.0.7` (ไม่มี License Text ที่สแกนพบ) การไม่มี Declaration ใน Wheel ไม่ใช่ข้อพิสูจน์ว่าไม่มีสิทธิ์ แต่ต้องตรวจหลักฐาน License ที่ต้นทางก่อนแจกจ่าย

มี Wheel ที่ระบุ Copyleft โดยตรง ได้แก่ `phonemizer 3.6.0` (GPLv3+), `phonemizer-fork 3.3.2` (GPLv3+), `gensim 4.4.0` (LGPL-2.1-only) และ `num2words 0.5.6` (LGPL) โดยยังต้องตรวจเงื่อนไขจริงรายโปรแกรม/ไบนารี

**ข้อแตกต่างที่สำคัญ:** NumPy และ SciPy ประกาศ License หลักเป็น BSD แต่มีข้อความ License ของบุคคลที่สามรวมอยู่ใน METADATA การตรวจจึงแยกป้าย `embedded-third-party-copyleft-notices-review` ไม่จัดทั้ง Wheel เป็น GPL อัตโนมัติ

หลักฐานรายละเอียดอยู่ที่ `cache/v4-qa-candidates/rights-wheel-audit-20261120.json` (ไฟล์ QA ภายใน ไม่ติด Git) สามารถสแกนซ้ำด้วย `scripts/audit_v4_wheel_licenses.py` โดยไม่มีการติดตั้งแพ็กเกจระหว่างตรวจ

## หลักฐานจากต้นทาง (ตรวจสอบ URL ได้)

- MakHamTTS: https://huggingface.co/pythainlp/MakHamTTS — Apache-2.0
- Dataset MakHam: https://huggingface.co/datasets/pythainlp/MakHamTTS-dataset — CC BY 4.0
- Paradee: https://github.com/sahilmahendrakar/paradee — Apache-2.0
- PyThaiTTS/FastThaiG2P: https://github.com/PyThaiNLP/PyThaiTTS และ https://github.com/awslabs/FastThaiG2P — ตรวจข้อมูลแต่ละส่วนแยกจากกัน
- Melo Chinese: https://huggingface.co/myshell-ai/MeloTTS-Chinese — MIT
- sherpa-onnx Melo export: https://github.com/k2-fsa/sherpa-onnx/blob/master/scripts/melo-tts/export-onnx.py
- Supertonic 3: https://huggingface.co/Supertone/supertonic-3 — OpenRAIL-M
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M — Apache-2.0
- Vachana: https://huggingface.co/VIZINTZOR/VachanaTTS — MIT model card
- Wayu Paxa Edge: https://huggingface.co/wayu-ai/wayu-paxa-tts-edge — CC BY-NC 4.0 พร้อม Acceptable Use
- Wayu inference: https://github.com/wayu-research/wayu-tts-inference — inference code Apache-2.0 แยกจาก weights
- M2M100: https://huggingface.co/facebook/m2m100_418M — MIT

**ที่ต้องตรวจเพิ่มเติมก่อนอนุมัติจริง:** ตรวจไฟล์ `assets/legal/` ที่บรรจุในแต่ละ v4 Archive, ตรวจ Metadata License/SPDX/License Text ของ Wheel ทุกไฟล์ รวมถึง Native DLL/EXE; ยืนยันสิทธิ์ของเสียง/ชุดข้อมูลฝึกและสคริปต์แปลงโมเดล; ทำ Third-Party Notices/Source Offer ตามแต่ละ License; ให้ผู้รับผิดชอบตรวจเงื่อนไข Redistribution ฉบับเต็ม

## Release Gate และหลักการไม่ผูกกับ Core

- `src/voxweavetts/provider_rights.py` เป็น **ทะเบียนสิทธิ์ของแพ็กเกจ v4 ที่ทีมเป็นผู้จัดทำ** ไม่ใช่รายชื่ออนุญาตให้ผู้ใช้ติดตั้ง โมเดลใหม่จากผู้ใช้ไม่ต้องรอ Update VoxWeave เพื่อใช้งาน
- `scripts/verify_v4_model_inventory.py --deep` เป็นการตรวจความถูกต้องของไฟล์ทางเทคนิคเท่านั้น
- `scripts/verify_v4_model_inventory.py --require-cleared` และ `scripts/Generate-Release-Checksums.ps1` ต้อง **BLOCK Public Model Release** ในระหว่างที่ยังไม่ได้ตรวจสิทธิ์ครบ
- `dist/ModelPackagesV4-QA/` ยังคงเป็นไฟล์ **UNRELEASED-QA** ของเครื่องพัฒนา ไม่มีไฟล์เหล่านี้อยู่ใน GitHub Release หรือ Commit
- `dist/VoxWeaveTTS-v0.12.0-dev0-portable.zip` เป็น Build QA ที่มี MakHam v4 แบบทดลองและมีข้อจำกัดสิทธิ์เช่นกัน **ยังไม่ได้เผยแพร่**
- Public GitHub Release v0.11.0 เป็นประวัติย้อนหลังของ v3 เท่านั้น ไม่ใช่หลักฐานสิทธิ์ของแพ็กเกจ v4

## แนวทางถัดไป

ให้เริ่มจากสแกน License Metadata ของ Wheel ภายใน v4 Archive ทีละโมเดล และแยก Critical Blockers (`vachanatts`, `phonemizer`, `espeakng-loader`, `wayu-tts`) จากแพ็กเกจที่น่าจะจัด Notices ได้ง่ายกว่า หลังจากนั้นจึงปรับสถานะ Release Gate เมื่อมีหลักฐานของไฟล์ที่จะแจกจริงครบถ้วน ไม่อนุมัติเพียงเพราะ Manifest ระบุ MIT หรือ Apache-2.0
