# VoxWeaveTTS — เกณฑ์ Release เมื่อโมเดลครบทุกตัว (v3)

**สถานะตรวจล่าสุด: 20 พฤศจิกายน 2026 — ยังไม่พร้อมออก Release รุ่นที่ระบุว่า "โมเดลครบ"**

## โมเดลที่ต้องมีทั้งหมด

ต้องมีไฟล์ Universal `.vwmodel` v3 **8 ตัว** (เสียง TTS 7 ตัว + Translation 1 ตัว) ที่ติดตั้งแบบออฟไลน์ได้จริงจากไฟล์เดียว ไม่ต้องดาวน์โหลด Dependencies ไม่ต้องรัน Installer เก่า และไม่มี fallback v2:

| Model | v3 ใน Release v0.11.0 | หมายเหตุ |
| --- | --- | --- |
| MakHam Paradee | มี | โมเดลเริ่มต้น |
| FastThaiG2P Thai Som | มี | ทดสอบสร้าง WAV จริงแล้ว |
| Melo Chinese | มี | ทดสอบติดตั้ง Runtime แชร์แล้ว |
| Supertonic 3 | มี | ทดสอบสร้าง WAV จริงแล้ว |
| M2M100 418M | มี | ติดตั้งออฟไลน์ได้ แต่ Inference ยังถูกปฏิเสธเพราะ Windows RAM/Commit ไม่พอ |
| **Vachana Thai 4 Voices** | **ขาด** | QA: Model Asset + 14 Wheel ทำเป็นแพ็กเกจ v3 ได้ แต่ `ssg 0.0.8` Wheel บรรจุ `.data/scripts/ssg-cli` จึงถูก Security Gate ห้ามรัน; `vachanatts 0.0.7` Wheel ไม่ได้ประกาศ License/มี License Text ครบ |
| **Kokoro 82M Multilingual INT8** | **ขาด** | QA: Asset + 31 Candidate Wheels ทำเป็นแพ็กเกจ v3 ได้ แต่ Candidate มี Misaki 0.9.4 / pyopenjtalk ต่างจากสูตรที่แก้ Windows เป็น Misaki 0.8.0; GPL-3.0-or-later ของ phonemizer, eSpeak NG และ Native Notices ยังต้องปฏิบัติตามเงื่อนไขก่อนเผยแพร่ |
| **Wayu Paxa Edge NC (12 Voices)** | **ขาด** | ไม่มีชุด Wheel ออฟไลน์ที่ครบและตรวจสิทธิ์แล้ว; Recipe เดิมยังมี Git/Direct URL และ Dependencies หลายชุด; Model Weights ใช้ **CC BY-NC 4.0** เท่านั้น ต้องยืนยันคำเตือน NonCommercial แยกทุกครั้ง |

**การทำ Manifest v3 หรือบรรจุ SHA-256 ผ่านไม่ใช่หลักฐานว่าใช้ Runtime ได้:** ต้องผ่าน Trusted Wheel Hash ในตัวโปรแกรม, ติดตั้งจากไฟล์เดียวบนเครื่องออฟไลน์, สร้าง WAV จริง, ทดสอบย้ายโฟลเดอร์และถอนติดตั้งโดยไม่ทำลาย Runtime อื่น

## งานที่ทำไปในรอบแก้ช่องว่าง

- รักษาไฟล์ต้นฉบับ v1/v2 ของโมเดลไว้ **ไม่ลบหรือเปลี่ยน** เพื่อให้ตรวจ SHA-256 ของ Asset เทียบแหล่งที่มาได้
- เพิ่ม `scripts/prepare_missing_v3_candidates.py` อ่านไฟล์เก่าแบบข้อมูล (ไม่ execute, ไม่เอาโค้ดเก่ากลับมาใช้ที่ Runtime), ตรวจ SHA-256 ของแต่ละ Asset, สร้าง v3 Candidate ในโฟลเดอร์ **`cache/v3-unreleased-candidates` เท่านั้น** พร้อม Rights=`hold`
- QA สร้างไฟล์ Candidate ของ Vachana (~278 MiB) และ Kokoro (~196 MiB) มี Wheel ทั้งชุดที่พบในเครื่อง แต่ **ยังติดตั้ง/เผยแพร่ไม่ได้**, ไม่มีการเพิ่ม App-owned Approved Lock ลง `scripts/wheelhouse-locks`
- ระหว่างทดสอบ Runtime ของ Vachana ด้วย Temporary QA Approval (เฉพาะ Portable ทดสอบ) พบ `OfflineRuntimeError: unsafe executable or path inside wheel` เพราะ `ssg-cli`; ระบบจึงปฏิเสธ Wheel ตามกฎ v3 โดยถูกต้อง และล้าง Approval ทดสอบออก
- เพิ่ม `scripts/verify_complete_v3_release.py` เป็น Release Gate แบบอ่านอย่างเดียว: ต้องครบ 8 โมเดล, Format v3, Adapter ตรง, App-approved Offline Wheels และไม่มี First-party Publication HOLD; หากไม่ครบจะคืน **exit code 2**
- เพิ่ม `tests/test_v3_full_model_release_gate.py` เพื่อป้องกันการแสดงว่า Release ครบเมื่อยังขาดโมเดล หรือเมื่อ Wheel อยู่ในสถานะ HOLD

## งานที่ต้องแก้ก่อนออก Release ถัดไป

1. **Vachana**: ขอ/ตรวจสิทธิ์ที่ครอบคลุม `vachanatts` Wheel จริง หาวิธีสร้าง Wheel ที่ไม่บรรจุ Installer Script และไม่ทำให้ฟังก์ชัน TTS เปลี่ยน (เช่น Rebuild จาก Source ที่มี License พร้อมตรวจ SHA ใหม่) จัด Trusted Offline Lock พร้อม Notices แล้วทดสอบทั้งสี่เสียง
2. **Kokoro**: สร้าง Closure แบบ Pin Misaki 0.8.0 และ UniDic Lite 1.0.8 สำหรับ Windows x64/Python 3.11 จาก Wheel ที่แจกได้ จัดการสัญญาอนุญาต GPL/Native Code อย่างถูกต้องและทดสอบเสียง EN/JA จริง
3. **Wayu NC**: จัด Offline Wheel Closure รวม VCS/Direct URL ที่อนุญาตให้แจกจ่าย ตรวจ License ของโค้ด/Weights/Dependencies, ฝังสิทธิ์ NonCommercial + Acceptable Use อย่างชัดเจน แล้วทดสอบทั้งเสียงไทย/อังกฤษและการถอนติดตั้ง
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
