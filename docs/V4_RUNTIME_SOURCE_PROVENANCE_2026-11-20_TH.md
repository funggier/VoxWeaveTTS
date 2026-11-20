# VoxWeaveTTS — Runtime Source Provenance (V4) รอบตรวจเพิ่มเติม

วันที่: 20 พฤศจิกายน 2026 · **QA เฉพาะการตรวจไฟล์จริง ไม่ใช่ใบอนุญาตแจกจ่ายใหม่**

## เป้าหมาย

ตรวจให้ทราบแน่ชัดว่าโมเดล V4 ใช้ **Wheel และ DLL ไฟล์ใด** และแนบสำเนาเอกสารจากผู้เผยแพร่ต้นฉบับที่ตรงกับเวอร์ชันนั้นโดยไม่แก้ไขโค้ดหรือโมเดล เอกสารนี้ต่อจาก [V4_NATIVE_COMPONENT_EVIDENCE_2026-11-20_TH.md](V4_NATIVE_COMPONENT_EVIDENCE_2026-11-20_TH.md)

แพ็กเกจที่เคยเผยแพร่เป็น V2/V3 มีน้ำหนักโมเดลตรงกับ V4 ตามรายงานเดิม แต่การเพิ่ม Wheel และ DLL เป็นการแจกจ่ายซอฟต์แวร์เพิ่มอีกชั้นหนึ่ง ไม่สามารถอ้าง License ของน้ำหนักแทน License ของ Runtime ได้

## 1. ONNX Runtime 1.31.1 — 4 โมเดล

ตรวจแพ็กเกจ MakHam Paradee, FastThaiG2P Thai Som, Kokoro Multilingual และ Vachana Thai Four Voices โดยใช้ `scripts/archive_v4_onnxruntime_131_notices.py`

- ทั้ง 4 โมเดลบรรจุ **Wheel `onnxruntime-1.31.1-cp311-cp311-win_amd64.whl` ที่ SHA-256 เดียวกัน**: `c3d91b5de31e2fc82d71bd65b2b22bddee8b49057a3a36338e9a868e0ea90c05`
- `onnxruntime/capi/onnxruntime.dll` SHA-256: `8482d2ee174e28504f99730fb01d6861575870283de4ed3a897ad39170d9a9b9`
- Windows FileVersion ของ DLL ที่สกัดจาก Wheel: `1.31.1.20261023.3.6af1a93`
- คัดลอก `LICENSE` MIT ต้นฉบับ (SHA-256 `2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c`)
- คัดลอก `ThirdPartyNotices.txt` ต้นฉบับ (SHA-256 `143764b952fdb1a7c69ce653bfba74a7744d6a8a573bfb73e235fba356c83de3`)
- คัดลอก `VERSION_NUMBER` ต้นฉบับที่ระบุ `1.31.1`

ลิงก์เอกสารจากต้นทาง (GitHub tag ผ่าน jsDelivr):

- https://cdn.jsdelivr.net/gh/microsoft/onnxruntime@v1.31.1/LICENSE
- https://cdn.jsdelivr.net/gh/microsoft/onnxruntime@v1.31.1/ThirdPartyNotices.txt
- https://cdn.jsdelivr.net/gh/microsoft/onnxruntime@v1.31.1/VERSION_NUMBER

หลักฐานและดัชนี SHA เก็บไว้ที่ `cache/v4-rights-evidence/runtime-sources/onnxruntime-1.31.1/` และเพิ่มเอกสารลงใน QA แพ็กเกจแยกที่ `dist/ModelPackagesV4-ORT131NoticeQA/` โดยไม่มีการแก้ Wheel, Worker หรือ Weight

คำสั่งตรวจอิสระ:

~~~powershell
.\.venv\Scripts\python.exe -X utf8 scripts\archive_v4_onnxruntime_131_notices.py
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_legal_packaging.py --repacked dist\ModelPackagesV4-ORT131NoticeQA --models makham-paradee fastthaig2p-thai-som kokoro-multilingual-int8 vachana-thai-four-voices --require-onnxruntime-131
~~~

ผลจริง: **4/4 แพ็กเกจ**, **97 Wheel ตามรายการใน 4 แพ็กเกจ**, **159 เอกสารสิทธิ์/ดัชนีใน QA**, ทุก SHA ที่ตรวจตรงต้นฉบับ `public_release_authorized=false`

ยังต้องตรวจองค์ประกอบ native/transitive อื่นของแพ็กเกจเหล่านี้ และข้อกำหนดของต้นทางโมเดล/ข้อมูลฝึกก่อนแจกจ่าย ชื่อ Git tag ถูกตรึงเป็นเวอร์ชัน `v1.31.1` แต่ **ยังไม่ได้พิสูจน์ immutable commit** ของ tag ในรอบนี้

## 2. vachanatts 0.0.7 — แยกสิทธิ์น้ำหนักโมเดลออกจากโค้ด

ตรวจด้วย `scripts/audit_v4_vachanatts_pypi_provenance.py` โดยใช้ Wheel ที่บรรจุใน V4 จริง และ sdist ที่ดาวน์โหลดจาก PyPI (เก็บใน `cache/v4-rights-evidence/vachanatts-0.0.7/`)

- ไฟล์ Wheel SHA-256 `87244b82bc15711558ca5fd735379f3b77887ec655254c80ff6ad99c57686ad6` ตรงกับ PyPI: https://pypi.org/project/vachanatts/0.0.7/
- sdist `vachanatts-0.0.7.tar.gz` SHA-256 `c5e203446242076d70e61d1ca109d721e0bb031824dc93fed3d182db67a80bad`
- ไฟล์ซอร์ส **16/16** ภายใน `vachanatts/` มีเนื้อหาตรงกับ sdist แบบไบต์ต่อไบต์
- Wheel มี namespace `vachanatts1/` **อีก 9 ไฟล์ Python** ซึ่งไม่ได้อยู่ใน sdist (6 ไฟล์ตรงกับชื่อคู่ใน `vachanatts/` และอีก **3 ไฟล์ต่างกัน**)
- ทั้ง Wheel Metadata และ sdist `PKG-INFO` **ไม่พบ License / License-Expression** ที่ระบุสิทธิ์โค้ด และใน sdist ไม่พบไฟล์ชื่อ LICENSE, COPYING หรือ NOTICE
- GitHub [VYNCX/VachanaTTS2](https://github.com/VYNCX/VachanaTTS2) ที่เกี่ยวข้องเปิดซอร์สให้เห็น แต่ไม่พบเอกสาร `LICENSE` ใน root ของ default branch จากการตรวจนี้ สิทธิ์นำโค้ดไปแจกจ่ายจึงยังต้องตรวจหรือขอคำยืนยันต้นทาง
- คำอธิบายของแพ็กเกจให้เครดิต [Piper](https://github.com/OHF-Voice/piper1-gpl) ว่าเป็นแหล่งอ้างอิงโค้ดหลัก/การฝึก; Piper engine มี License GPL-3.0-or-later แต่ข้อมูลนี้ **ยังไม่เพียงพอที่จะสรุปว่าไฟล์ `vachanatts` ทุกไฟล์เป็นอนุพันธ์ GPL** ต้องระบุที่มาของโค้ดที่ใช้งานจริงเป็นรายไฟล์
- License `MIT` ของ [น้ำหนักโมเดล Vachana](https://huggingface.co/VIZINTZOR/VachanaTTS) ยังคงเดิมและ **ไม่ได้ใช้เป็นข้ออ้างว่า Wheel โค้ดทั้งหมดเป็น MIT**

ดัชนีตรวจอยู่ที่ `cache/v4-rights-evidence/runtime-sources/vachanatts-0.0.7/INDEX.json` และตั้ง `code_license_not_verified=true`, `public_release_authorized=false` **ไม่คัดลอก sdist ที่ยังไม่ทราบสิทธิ์ลงในไฟล์แจกสาธารณะ**

**สิ่งที่ต้องได้รับการยืนยันต่อ:** ผู้เผยแพร่ `vachanatts 0.0.7` อนุญาตแจกจ่ายและดัดแปลงโค้ดภายใต้เงื่อนไขใด, `vachanatts1` มีที่มาอย่างไร, ต้องทำตาม GPL ของ Piper หรือไม่ (หากมีการนำโค้ด GPL มาใช้จริง), และสิทธิ์ข้อมูลฝึก/เสียงจากต้นทาง

คำสั่งตรวจออฟไลน์:

~~~powershell
.\.venv\Scripts\python.exe -X utf8 scripts\audit_v4_vachanatts_pypi_provenance.py
~~~

## 3. ข้อสรุปสำหรับการปล่อยแพ็กเกจ

- เผยแพร่ **Core** ได้ตาม Release เดิม `v0.12.1`
- โมเดล **ยังเป็น QA เท่านั้น** จนปิดรายการสิทธิ์ครบตามไฟล์ที่แจกจริง ไม่ใช่เพราะจำเป็นต้องเป็น License เชิงพาณิชย์ทั้งหมด
- Wayu คง `CC BY-NC 4.0`; Supertonic คง OpenRAIL-M; น้ำหนักของโมเดลอื่นคงเงื่อนไขเดิม
- การคัดลอก LICENSE/NOTICE อย่างถูกต้องเป็นหนึ่งในข้อกำหนด ไม่ใช่การรับรองว่าครบทั้ง Corresponding Source, ผู้มีลิขสิทธิ์ และเงื่อนไขใช้งาน

**สถานะสุดท้ายของรอบนี้:** `public_release_authorized=false` สำหรับแพ็กเกจที่ยังไม่ผ่านการตรวจสิทธิ์ครบ ไม่มีการนำไฟล์ QA ขึ้น Release
