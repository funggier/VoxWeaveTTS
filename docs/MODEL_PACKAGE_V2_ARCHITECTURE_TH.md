# VoxWeaveTTS — Universal Model Package v2 (สถาปัตยกรรมและแผนต่อยอด)

**อัปเดต Phase A–B:** Native v2 และ Managed Runtime Pool แบบ Health Check/Offline Repair เริ่มใช้งานใน Source แล้ว · [คู่มือ Runtime Pool](MANAGED_RUNTIME_POOL_TH.md) · Native v2 เริ่มใช้งานใน Source แล้ว โดยเลิกใช้ Compatibility Bridge และปิดการติดตั้ง v1 ผ่าน Model Package Manager; รายละเอียด Schema ที่ใช้จริงและคำสั่งสร้างแพ็กเกจอยู่ที่ [Universal v2](UNIVERSAL_VWMODEL_V2_TH.md) ตัวอย่าง Concept ด้านล่างเป็นเพียงแนวคิดเก่าที่ไม่ใช่ Schema พร้อมใช้ทุกฟิลด์

สถานะ: **ทยอยใช้งานจริง (Runtime Registry / Uninstall Guard / MakHam managed package) + ข้อเสนอ Phase ถัดไป** · 2026-11-17. การติดตั้ง Wheelhouse และ Adapter จากแพ็กเกจแบบอัตโนมัติยังไม่ได้เปิดใช้งาน

## เป้าหมาย

เปลี่ยน `.vwmodel` จากที่เก็บน้ำหนักโมเดลเฉพาะประเภท ให้เป็นแพ็กเกจที่มีข้อกำหนดแบบข้อมูล (data-only metadata) สำหรับกำหนด **ประเภทโมเดล, Engine/Adapter, Runtime Environment, วิธีเตรียม Dependencies, License และการเชื่อมต่อ** โดยติดตั้งผ่านหน้าจอ Model Package Manager เดียว

- ใช้ได้กับ `tts`, `voice-cloning`, `stt`, `translation`, `llm`, และประเภทเพิ่มเติมในอนาคต
- ติดตั้งแบบ **reuse existing verified runtime / build new runtime / use verified bundled offline wheels** ตามแพ็กเกจและสิทธิ์การอนุญาต
- พกพาไปโฟลเดอร์อื่นหรือไดรฟ์อื่นได้ โดยตรวจพบการย้ายพาธและให้ผู้ใช้ยืนยันการ **recreate** Environment แบบ Offline จาก Trusted Recipe/Cache (ไม่ซ่อมอัตโนมัติเมื่อยังไม่ยืนยัน) เมื่อ environment เดิมอ้างอิงพาธเก่า (ไม่ถือว่าการย้าย Python venv ที่มี Scripts เป็น portable)
- ความสามารถในการรัน Code, Python Module, DLL หรือ Install Hooks ต้องผ่าน Trusted Adapter Registry และการยืนยันของผู้ใช้ ไม่อนุญาตให้ Manifest ที่ยังไม่เชื่อถือระบุคำสั่ง Shell/URL executable แล้วทำงานอัตโนมัติ
- ไม่เปลี่ยน User Settings, Voice Preset, Translation Prompt, Route หรือโมเดลเดิมในการ Upgrade โดยไม่ตั้งใจ

## แยกสามองค์ประกอบ

1. **Model Assets (Model Package):** Weights (.onnx/.safetensors/.pth หรืออื่น ๆ ที่อนุญาตเฉพาะ Adapter), tokenizer, voices, configuration, language/voice capability, license และ upstream provenance
2. **Adapter (capability):** โค้ดที่เชื่อถือได้ซึ่งให้ API `synthesize/translate/transcribe` และประมวลผลใน Worker ของตัวเอง; `adapter.id` ต้องมาจาก allowlisted built-in หรือ externally signed/approved provider ไม่ใช่ imports อิสระจาก Zip
3. **Runtime Environment:** Python interpreter ABI, OS/platform, CPU/CUDA/DirectML, dependency lock, pinned wheel hashes, optional platform wheelhouse, healthcheck, cache policy และ installer recipe ที่ **trusted engine code** ตีความเป็น Allowlist เท่านั้น

## Manifest v2 (ตัวอย่างเชิงสัญญา ยังไม่เปิดใช้)

```json
{
  "format": "voxweavetts.model-package",
  "format_version": 2,
  "package": {
    "id": "m2m100-418m",
    "version": "1.0.0",
    "kind": "translation",
    "title": "M2M100 418M",
    "languages": ["th", "en", "ja", "zh"]
  },
  "adapter": {
    "id": "m2m100-transformers-v1",
    "api_version": 1,
    "trust": "builtin"
  },
  "runtime": {
    "id": "python-torch-transformers-cpu",
    "kind": "python-venv",
    "python": "3.11",
    "platform": "windows-x64",
    "accelerator": "cpu",
    "install_policy": "reuse-or-create",
    "lockfile": "runtime/locks/win-x64-cpu.lock",
    "source": "bundled-wheels-or-verified-download"
  },
  "assets": "manifest-assets.json",
  "rights": "legal/rights.json"
}
```

ตัวอย่างนี้เป็นเพียง Schema Concept; ไม่ได้กำหนดให้ M2M100 ต้องใช้ทุกภาษาในตัวอย่าง หากต้องการประกาศภาษาจริงให้ใช้รายการที่รองรับและทดสอบแล้ว. ไฟล์ `manifest-assets.json` และ `legal/rights.json` ต้องตรวจ SHA-256 ด้วยตารางไฟล์กลางก่อนใช้งาน.

## Runtime Registry และการนำกลับมาใช้

Environment Identity หรือ **runtime fingerprint** ต้องคำนวณจาก:
- OS/architecture เช่น Windows x64; Python ABI/patch compatibility; accelerator/driver compatibility CPU หรือ CUDA
- Adapter API version และ Dependency Lock ที่มี Version + SHA-256 ครบทุก Wheel
- Runtime security policy/permissions; trusted recipe version

ให้ลงทะเบียน Managed Runtime ใน `runtime/environments/<fingerprint>/` และมี Registry แบบ Transactional ภายใน `data/runtime-registry.json` (ย้ายได้โดยใช้ Relative Path ไม่ใช่ Absolute Path)

การติดตั้งแพ็กเกจใหม่: ถ้า Runtime Fingerprint ตรงกับ Runtime ที่ตรวจสถานะและ Health Check ผ่านแล้วให้ **Reuse** โดยเพิ่ม Reference Count; ถ้าไม่ตรง ให้สร้าง Environment ใหม่แยกกัน ป้องกัน Dependency Version Conflict. ไม่ดึง Python System/Global Site-Packages มาใช้โดยเงียบ. Sharing Wheel Cache กับ Sharing Runtime เป็นคนละเรื่อง; Shared Cache อนุญาตได้แม้ Environment จริงคนละอัน

เมื่อถอนโมเดลให้ลบเฉพาะ Model Assets กับการอ้างอิง Runtime; **ไม่ลบ Runtime ถ้ายังมีโมเดลอื่นใช้อยู่**; Runtime ที่ไม่มีการใช้งานให้ผู้ใช้กดยืนยันก่อนลบหรือทำ Garbage Collection อย่างปลอดภัย

## Runtime ส่งมากับ .vwmodel ได้อย่างไร

- `recipe-only` — เล็กที่สุด เก็บรายการ Dependencies และ Hash พร้อม Trusted Provider ID; เมื่อกดติดตั้ง Runtime จึงเรียก uv ลง Managed venv
- `bundled-wheels` — สำหรับ Offline Portable ให้ใส่ Wheelhouse สำหรับ OS/Python ABI ที่รองรับ และ Lock + Hash มาด้วย; โปรแกรมตรวจ SHA ทุก Wheel ก่อนให้ Trusted Runtime Installer ติดตั้งด้วย `--offline --no-index`; Dependencies หรือ Install Script ของ Wheel ถือเป็นโค้ดที่ต้องขอความยินยอม
- `prebuilt-runtime` — **ไม่แนะนำเป็นค่าปริยาย** เพราะ Windows venv ไม่รับประกันการย้ายไดรฟ์หรือโฟลเดอร์; หากรองรับต้องเป็น Runtime Bundle ที่สร้างตามสเปกโดยเฉพาะ มี Rebase/Rebuild/Health Check เมื่อย้ายพาธ
- `reuse-only` — ใช้ Runtime ที่มีใน Managed Registry แล้วเท่านั้น หากไม่มีให้แสดง Missing Runtime ไม่ติดตั้งอะไรอัตโนมัติ

หาก Engine/Adapter เองยังไม่มีอยู่: ให้แสดง **Missing Trusted Adapter** และช่อง **ติดตั้ง Adapter ที่อนุมัติ/มีลายเซ็น** แยกจากการติดตั้งข้อมูลโมเดล ห้าม Import โมดูลใหม่จาก Archive โดยอัตโนมัติ ไม่ว่ามี Manifest หรือไม่

## ขั้นตอนติดตั้งแบบปลอดภัย

1. อ่านเฉพาะ ZIP index + bounded Manifest/Signature ตรวจประเภท `tts/translation/...`, ขนาดไฟล์, OS/ABI, ประเภท/ขอบเขตของ License และ Trust
2. ตรวจทุก Asset/Lock/Wheel ตาม Allowlist, SHA-256, Expansion Ratio, ความจุดิสก์, ชื่อไฟล์, Path Traversal, Symlinks, Duplicate Entries, และ Binary Type
3. แสดงแผนติดตั้งชัดเจน: **Model Assets**, **Runtime ที่จะ Reuse/สร้าง**, ปริมาณดาวน์โหลด/ดิสก์, Source, สิทธิ์, และความเสี่ยงจากการติดตั้ง Dependencies
4. ตรวจว่ามี Compatible Managed Runtime หรือไม่ หากไม่มีและผู้ใช้อนุญาตจึงสร้างใหม่แบบ Atomic ใน `runtime/environments/.staging-...`, ติดตั้ง Wheel จาก Offline Bundle หรือตาม Trusted Lock
5. Health Check ด้วย Interpreter/Adapter API ที่อนุมัติ, ตรวจ Model Asset Readiness และสิทธิ์ของโมเดล จากนั้น Atomic Rename/Registry Commit
6. **Rollback ทั้ง Runtime ที่กำลังสร้างและ Model Stage** เมื่อผิดพลาด แต่ไม่ลบ Runtime/Model อื่น, ไม่แก้ System Python, ไม่แตะ Ollama หรือ Data/Presets ของผู้ใช้
7. UI แสดง `Model installed` / `Runtime missing` / `Installing Runtime` / `Ready` / `Rejected` แยกอย่างถูกต้อง มี Progress, Error Code และ Logs โดยไม่เปิดเผยข้อมูลส่วนตัว

## ส่วนที่ลงมือทำใน Source หลัง v0.9.4

- `runtime_registry.py` สร้างรายการ Runtime สำหรับ Provider TTS และ M2M100 โดยตรวจ Dependencies Recipe และ Runtime Fingerprint รวมถึงนับโมเดลที่อ้างอิงอยู่จริงจากแพ็กเกจที่ติดตั้งและโมเดล Legacy
- หน้า **Model Package Manager → Runtime Environment Registry** แสดงรายการ Runtime, จำนวนโมเดลที่อ้างอิงและสถานะพร้อมใช้งาน; ปุ่มถอน Runtime ถูกปิดเมื่อมีโมเดลใดใช้อยู่ และ API `/v1/runtimes/remove` ตรวจ Origin/Intent, Fingerprint และจำนวน Consumer ซ้ำก่อนลบ
- **MakHam Paradee** ใช้ Engine ID เดิม `makham-paradee-cpu` แต่มีแพ็กเกจ `VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0.vwmodel`; Build Portable ติดตั้งแพ็กเกจนี้ใน `models/packages/makham-paradee/1.0.0/` ตั้งแต่แรก และเก็บไฟล์กู้คืนไว้ต่างหาก
- รองรับการถอนแพ็กเกจ MakHam หรือไฟล์ Legacy รุ่นเก่าที่ตรวจสอบ SHA-256 ถูกต้อง; หลังถอนจะไม่กลับไปโหลดน้ำหนัก Legacy ที่เหลืออยู่โดยไม่ตั้งใจ
- โค้ด Engine/Provider และ Python Runtime ไม่ถูกลบพร้อมน้ำหนักโมเดลโดยอัตโนมัติ; Runtime จะลบแยกได้หลังไม่มี Consumer
- M2M100 Runtime แบบแยก Environment และการเลือกตัวติดตั้ง AI/TTS จาก `.vwmodel` เดียวกันเป็นพื้นฐานให้ขยายต่อ

**ส่วนที่ยังไม่เสร็จ:** Runtime Fingerprint ปัจจุบันใช้ตรวจและป้องกันการลบสภาพแวดล้อมที่มีการใช้ร่วมกันใน Provider เดียว ยังไม่ได้รวม Runtime จาก Provider คนละตัวที่ Dependencies บังเอิญเข้ากันได้ และยังไม่ได้เปิดใช้ v2 Manifest/Offline Wheelhouse จาก Third-party Model Package โดยตรง

## แผนการย้ายระบบปัจจุบัน

**Phase A:** เพิ่ม Universal Model Package Registry + v2 Manifest Validator + Runtime Fingerprint/Resolver (อ่าน v1 TTS และ v1 AI เดิมต่อไปได้). ทำการค้นหาตัวติดตั้งโดย Manifest format ปัจจุบันให้ถูกก่อน

**Phase B:** เพิ่ม Environment Pool/Installer สำหรับ Built-in Trusted Adapters ก่อน เช่น M2M100 `translation`, Wayu `tts`, Kokoro `tts`; ตรวจ Reuse จาก Lock Fingerprint ที่ตรงเท่านั้น

**Phase C:** เพิ่ม Optional Offline Wheelhouse พร้อม SHA + User Approval. ป้องกันการรัน Code จาก Model Zip ที่ยังไม่ Verified

**Phase D:** เพิ่ม Signed Third-party Adapter Packages, Public SDK, Compatibility Matrix, Migration/Uninstall/GC และ Stress Tests สำหรับ CPU/RAM/VRAM/Multiple Workers

## กติกาความเข้ากันได้และความปลอดภัย

- **v1 ที่ติดตั้งไปแล้วต้องไม่แตก**: ตั้งค่า/Route/Voice Preset/Model Packages เดิมยังใช้ได้; v2 สามารถใช้ Universal UI โดยไม่ต้อง Rewrite v1 Archive
- ให้ Archive เก็บ Dependency Recipe ไม่ใช่ Shell Script ที่รันเอง; ห้าม URL Download แบบไม่ตรวจ Hash, Install Hooks อิสระ และ Dynamic Imports จากแชท
- ภาษา/ความสามารถที่ Model ประกาศเป็น **capabilities** และสามารถใส่ `verified/experimental` ต่อภาษาได้ โดยไม่จำเป็นต้องกีดกันโมเดลอ่านอังกฤษที่ทดสอบแล้ว
- แยกสิทธิ์ Model Weights, Adapter Code และ Third-party Wheels ไม่ถือว่า License ของ Framework ส่งผลให้โมเดลใช้เชิงพาณิชย์ได้
- ไม่แก้ Pagefile / ปิด Ollama อัตโนมัติหาก M2M100 เกิด Windows Error 1455; แสดง Memory Commit และทางเลือกให้ผู้ใช้ตัดสินใจ

**สาระสำคัญ:** .vwmodel v2 ควรเป็น **Declarative Package + Optional Verified Runtime Materials**, ส่วนโปรแกรมเป็น **Trusted Installer + Reusable Environment Registry**. ออกแบบให้ขยายได้โดยไม่เปิดสิทธิ์รันโค้ดจากโมเดลใด ๆ อย่างไม่มีขอบเขต
