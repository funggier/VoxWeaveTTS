# VoxWeaveTTS — เกณฑ์ Release เมื่อโมเดลครบทุกตัว (v3)

**สถานะตรวจล่าสุด: 20 พฤศจิกายน 2026 — ยังไม่พร้อมออก Release รุ่นที่ระบุว่า "โมเดลครบ"**

## ผลทดสอบเพิ่มเติม 20 พฤศจิกายน 2026 — ทางเทคนิคผ่านแล้วใน QA

**Vachana, Kokoro และ Wayu NC ผ่านการติดตั้งแบบออฟไลน์จากไฟล์ `.vwmodel v3` และสร้างเสียงจริงใน Portable ทดสอบแยกครบทั้งสามโมเดลแล้ว** โดยยังไม่สามารถเผยแพร่เป็นชุดสมบูรณ์ เพราะการตรวจสิทธิ์และ Provenance ของ Dependencies บางตัวยังค้างอยู่

| โมเดล | สิ่งที่ผ่าน | ขอบเขต |
| --- | --- | --- |
| Vachana | 14 Wheel, Scriptless `ssg` QA, ติดตั้ง, สร้างเสียง `th_f_1` ที่ 22,050 Hz, ถอนและล้าง Runtime/QA Lock | ยังไม่ผ่านการตรวจ License ของ `vachanatts 0.0.7` |
| Kokoro | 31 Wheel, Scriptless `plac` QA, ติดตั้ง, ตรวจพบ 18 เสียง, สร้าง WAV `af_heart` อังกฤษและ `jf_nezumi` ญี่ปุ่น 24,000 Hz, ถอนและล้าง Runtime/QA Lock | แก้ G2P ให้เลือก `unidic-lite` เมื่อ `unidic` ไม่มี Dictionary จริง; ยังต้องตรวจ GPL/Native Notices |
| Wayu Paxa Edge NC | 106 Wheel (~467 MiB), ติดตั้งไฟล์เดียวแบบออฟไลน์, ตรวจพบ 12 เสียง, สร้าง WAV `f_young_warm` ไทยและ `m_young_clear` อังกฤษ 24,000 Hz, ถอนและล้าง Runtime/QA Lock | น้ำหนักโมเดลยังเป็น CC BY-NC 4.0; `phonemizer-fork` และ 5 Wheel ที่ไม่บรรจุ License Text ต้องประเมินการแจกจ่าย |

การลบสคริปต์ CLI/`.pth` จาก Wheel ทำ **เฉพาะชุด QA ที่สร้างใหม่ภายใน Cache**, เก็บ SHA-256 ของต้นฉบับและอัปเดต RECORD/Hash ใหม่ตามมาตรฐาน Wheel ไม่มีการแก้ไฟล์ Wheel ต้นฉบับ ไม่มีการลดยามตรวจ `_verify_trusted_wheels` และ **ไม่มีการนำ Temporary Trusted Lock ลง Source, Portable สำหรับ Release หรือ GitHub**

ในส่วน Wayu ได้สร้าง `wayu-tts 0.1.0` Wheel จาก `wayu-research/wayu-tts-inference` ที่ Git Commit `07ab898d516649313926f0b843b809a962f993ad` และดึง Dependencies มา **ระหว่างพัฒนา** เท่านั้น; Installer ของผู้ใช้ยังไม่เชื่อมต่อเครือข่าย การเพิ่มจำนวนรายการ Dependency สูงสุดจาก 100 เป็น `MAX_FILES` ไม่ได้เพิ่มจำนวนไฟล์ทั้งหมดที่ระบบอนุญาต

**M2M100 เพิ่มเติม:** เมื่อมีหน่วยความจำพร้อมใช้งาน QA ทำการติดตั้งโมเดลแปลภาษาจริง 418M จากแพ็กเกจ v3 ออฟไลน์, แปล `Good morning.` → `สวัสดีเช้า` และ `ขอบคุณครับ` → `thank you.` สำเร็จแล้ว ก่อนถอนติดตั้งทั้งหมด ผลนี้ตรวจการทำงานและภาษาปลายทาง แต่ยังไม่รับรองคุณภาพการแปลเชิงความหมาย

**รุ่นที่เผยแพร่:** v0.11.0 ยังมีเพียง 5 แพ็กเกจดังเดิม สถานะ `review_required`/`hold` หมายถึง **ยังไม่รับรองสิทธิ์การแจกจ่าย** ไม่ใช่ TTS ไม่ทำงาน รายงาน `scripts/verify_complete_v3_release.py` ยังคงต้องคืนผล BLOCKED จนกว่าจะมีไฟล์ Release จริงและมีหลักฐานสิทธิ์ครบ

## โมเดลที่ต้องมีทั้งหมด

ต้องมีไฟล์ Universal `.vwmodel` v3 **8 ตัว** (เสียง TTS 7 ตัว + Translation 1 ตัว) ที่ติดตั้งแบบออฟไลน์ได้จริงจากไฟล์เดียว ไม่ต้องดาวน์โหลด Dependencies ไม่ต้องรัน Installer เก่า และไม่มี fallback v2:

| Model | v3 ใน Release v0.11.0 | หมายเหตุ |
| --- | --- | --- |
| MakHam Paradee | มี | โมเดลเริ่มต้น |
| FastThaiG2P Thai Som | มี | ทดสอบสร้าง WAV จริงแล้ว |
| Melo Chinese | มี | ทดสอบติดตั้ง Runtime แชร์แล้ว |
| Supertonic 3 | มี | ทดสอบสร้าง WAV จริงแล้ว |
| M2M100 418M | มี | QA 20/11/2026 ผ่านติดตั้งออฟไลน์และแปล EN→TH / TH→EN จริง; ความเป็นธรรมชาติยังไม่ดีทุกประโยค (เช่น Good morning → สวัสดีเช้า) จึงยังเป็นรุ่นทดลอง |
| **Vachana Thai 4 Voices** | **ขาด** | QA v3 ผ่านการติดตั้งออฟไลน์และเสียงไทยจริง หลังสร้าง Wheel `ssg` สำหรับ QA แบบไม่มี CLI; ยังไม่ผ่าน License ของ `vachanatts 0.0.7` |
| **Kokoro 82M Multilingual INT8** | **ขาด** | QA v3 ผ่านติดตั้งออฟไลน์และ WAV อังกฤษ/ญี่ปุ่น หลังแก้ UniDic Lite; GPL-3.0-or-later ของ phonemizer และ Native Notices ยังต้องปฏิบัติตามเงื่อนไขก่อนเผยแพร่ |
| **Wayu Paxa Edge NC (12 Voices)** | **ขาด** | QA v3 มี Wheel 106 รายการติดตั้งออฟไลน์และ WAV ไทย/อังกฤษได้จริง แต่ยังต้องตรวจ GPL/License ของ Runtime ก่อนแจก และน้ำหนักเสียงจำกัด **CC BY-NC 4.0** |

**การทำ Manifest v3 หรือบรรจุ SHA-256 ผ่านไม่ใช่หลักฐานว่าใช้ Runtime ได้:** ต้องผ่าน Trusted Wheel Hash ในตัวโปรแกรม, ติดตั้งจากไฟล์เดียวบนเครื่องออฟไลน์, สร้าง WAV จริง, ทดสอบย้ายโฟลเดอร์และถอนติดตั้งโดยไม่ทำลาย Runtime อื่น

## งานที่ทำไปในรอบแก้ช่องว่าง

- รักษาไฟล์ต้นฉบับ v1/v2 ของโมเดลไว้ **ไม่ลบหรือเปลี่ยน** เพื่อให้ตรวจ SHA-256 ของ Asset เทียบแหล่งที่มาได้
- เพิ่ม `scripts/prepare_missing_v3_candidates.py` อ่านไฟล์เก่าแบบข้อมูล (ไม่ execute, ไม่เอาโค้ดเก่ากลับมาใช้ที่ Runtime), ตรวจ SHA-256 ของแต่ละ Asset, สร้าง v3 Candidate ในโฟลเดอร์ **`cache/v3-unreleased-candidates` เท่านั้น** พร้อม Rights=`hold`
- QA สร้าง Candidate ของ Vachana (~278 MiB), Kokoro (~196 MiB) และ Wayu NC (~751 MiB) และทดสอบ **ติดตั้งออฟไลน์ + สร้าง WAV จริง + ถอนติดตั้ง** สำเร็จทุกตัว แต่ **ยังเผยแพร่ไม่ได้** เพราะสิทธิ์ Dependencies ยังไม่ครบ ไม่มีการเพิ่ม Approved Lock ลง `scripts/wheelhouse-locks` ของโปรเจกต์หรือ Release
- ระหว่างทดสอบ Runtime ของ Vachana ด้วย Temporary QA Approval (เฉพาะ Portable ทดสอบ) พบ `OfflineRuntimeError: unsafe executable or path inside wheel` เพราะ `ssg-cli`; ระบบจึงปฏิเสธ Wheel ตามกฎ v3 โดยถูกต้อง และล้าง Approval ทดสอบออก
- เพิ่ม `scripts/verify_complete_v3_release.py` เป็น Release Gate แบบอ่านอย่างเดียว: ต้องครบ 8 โมเดล, Format v3, Adapter ตรง, App-approved Offline Wheels และไม่มี First-party Publication HOLD; หากไม่ครบจะคืน **exit code 2**
- เพิ่ม `tests/test_v3_full_model_release_gate.py` เพื่อป้องกันการแสดงว่า Release ครบเมื่อยังขาดโมเดล หรือเมื่อ Wheel อยู่ในสถานะ HOLD

## งานที่ต้องแก้ก่อนออก Release ถัดไป

1. **Vachana**: ขอ/ตรวจหลักฐานสิทธิ์ Redistribute `vachanatts` Wheel และกฎหมายที่เกี่ยวข้อง, ตรวจ QA Scriptless Wheel ก่อนใช้จริง, จัด App-approved Lock/Notices เฉพาะเมื่อสิทธิ์ครบ แล้วทดสอบเสียงทั้งสี่และย้ายโฟลเดอร์
2. **Kokoro**: สรุปสูตร Runtime (Misaki 0.9.4 + UniDic Lite fallback ผ่าน QA EN/JA แล้ว), ตรวจ GPL-3.0-or-later และสิทธิ์ Native/eSpeak/pyopenjtalk พร้อม Source/Notices ก่อนเผยแพร่ และทดสอบเสียงอื่น/Relocatable
3. **Wayu NC**: QA Offline Wheel Closure รวมโค้ดจาก Git Revision และ spaCy Model ผ่านติดตั้ง/เสียงไทยและอังกฤษแล้ว; ต้องตรวจสิทธิ์ Dependencies ทั้ง 106, GPL และ Wheel ที่ไม่มี License Text, จัด NC/Acceptable Use Notices และทดสอบ Relocatable/ทุกเสียงก่อนนำขึ้น Release
4. ตรวจ Integrity/License ทั้ง 8 แพ็กเกจด้วย Release Catalog ใหม่, ทดสอบ Relocatable ของทุก Runtime, ทดสอบ API/UI/CI, Build Portable และ SHA256 ใหม่
5. เมื่อ `verify_complete_v3_release.py` คืนผล PASS เท่านั้น จึงสร้าง **Release ถัดไป** ที่โมเดลครบ (ไม่แก้ไข Tag/Asset v0.11.0 เดิม)

## คำสั่งตรวจปัจจุบัน

```powershell
# รายงานโมเดล v3 ที่ขาด: ไม่มีการแก้ไฟล์หรือดาวน์โหลด
.\.venv\Scripts\python.exe -X utf8 scripts\verify_complete_v3_release.py --json

# ตรวจข้อมูลต้นฉบับ + Candidate Wheel (รายงานเท่านั้น)
.\.venv\Scripts\python.exe -X utf8 scripts\prepare_missing_v3_candidates.py

# สร้าง Candidate สำหรับ QA ใน Cache เท่านั้น, ไม่เผยแพร่ ไม่อนุมัติ Wheel
.\.venv\Scripts\python.exe -X utf8 scripts\prepare_missing_v3_candidates.py --prepare-drafts

# Regression Safety
$env:PYTHONPATH = 'src;tests'
.\.venv\Scripts\python.exe -m unittest -v test_v3_full_model_release_gate
```

**ข้อจำกัดเรื่องสิทธิ์:** Model Card ที่ระบุ MIT ไม่ใช่หลักฐานว่า Runtime Wheel ที่เผยแพร่แยกกันมีสิทธิ์ MIT; การกดยอมรับสิทธิ์ในแอปไม่ใช่การอนุญาตให้ผู้พัฒนาแจก Wheel ที่ไม่มีสิทธิ์ ตลอดจน GPL อนุญาตการใช้เชิงพาณิชย์ได้ภายใต้การปฏิบัติตามเงื่อนไข ไม่ใช่ "ห้ามใช้" โดยอัตโนมัติ

แหล่งที่ตรวจ: [Vachana Model](https://huggingface.co/VIZINTZOR/VachanaTTS), [vachanatts PyPI](https://pypi.org/project/vachanatts/0.0.7/), [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), [Wayu NC](https://huggingface.co/wayu-ai/wayu-paxa-tts-edge), [เอกสารสิทธิ์ Runtime เดิม](PROVIDER_RIGHTS_READINESS_TH.md)
