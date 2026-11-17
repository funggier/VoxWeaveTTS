# Universal .vwmodel v2 — Phase C: Offline Verified Wheelhouse

**สถานะ:** ระบบติดตั้ง/ซ่อมและทดสอบ Phase C อยู่ใน Source (หลัง v0.9.5) — **ยังไม่ได้ Release**

Wheelhouse เป็นชุด **ไฟล์ Dependencies สำหรับ Trusted Runtime** แยกจากไฟล์น้ำหนักโมเดลใน `.vwmodel v2` และแยกจาก `uv cache` ของเครื่องเดิม การติดตั้งจาก Wheelhouse ใช้ Python 3.11 และชุด Wheel ที่ตรงกับ OS/ABI ของเครื่องเท่านั้น ไม่รับคำสั่งติดตั้งหรือไฟล์รันจาก Model Package

## สถาปัตยกรรม

- `scripts/engine-dependencies/*.txt` และ `scripts/ai-dependencies/m2m100.txt` — Trusted Recipe จากโค้ดโปรแกรม
- `scripts/wheelhouse-locks/<runtime-id>.json` — Trusted Lock ใน Source: Runtime ID, Python ABI, Platform, Recipe SHA-256, ชื่อ Wheel, Version, ขนาด และ SHA-256 ของทุกไฟล์
- `runtime/wheelhouse/<runtime-id>/*.whl` — ไฟล์ Wheels ที่จัดเตรียมไว้แยกต่างหากและคัดลอกไปยังโฟลเดอร์โปรแกรมได้ (ไม่อยู่ใน Git Source)
- `cache/wheelhouse-drafts/` — Lock แบบร่างที่สร้างจากไฟล์ในเครื่อง **ยังไม่เป็น Trusted Lock**
- `cache/temp/` — สำเนา Wheels ชั่วคราวที่ตรวจสอบ Hash ระหว่างติดตั้ง; ลบทิ้งหลังใช้งาน

**Trusted Lock ที่ไม่มีไฟล์ Wheel ครบใช้ติดตั้งไม่ได้** และ **ไฟล์ Wheel ที่ไม่มี Trusted Lock ก็ใช้ติดตั้งไม่ได้** SHA-256 ช่วยป้องกันไฟล์ไม่ตรงกับ Lock แต่ไม่ใช่ลายเซ็นยืนยันตัวตนของผู้เผยแพร่ ผู้จัดทำโปรแกรมต้องตรวจที่มาและสิทธิ์แจกจ่ายก่อนยอมรับ Lock

## การติดตั้งจาก UI

ใน Runtime Registry จะแสดงสถานะ `wheelhouse`:

| สถานะ | ความหมาย |
|---|---|
| `not-published` | ยังไม่มี Trusted Lock สำหรับ Runtime |
| `recipe-unsupported` | Recipe ยังมี Direct URL / Git / Dependencies ที่ไม่ใช่ Exact Pin |
| `not-ready` | Lock/ไฟล์ไม่ครบ ไม่ตรง Recipe/OS หรือข้อมูลไม่ผ่านการตรวจเบื้องต้น |
| `present-unverified` | ไฟล์และขนาดตรง Lock แต่ **ยังไม่ได้ตรวจ SHA-256 ทุกไบต์** |

ปุ่ม **ติดตั้ง/ซ่อมด้วย Verified Wheelhouse** จะปรากฏเมื่อมี Wheelhouse ครบเบื้องต้น และ Runtime ยังไม่พร้อมใช้งาน ผู้ใช้ต้องยืนยันการดำเนินการผ่านหน้าโปรแกรม

Server ตรวจ Same-Origin, Intent และ `expected_fingerprint` ก่อนเปิดงานเบื้องหลัง คำขอรับได้เพียง `id`, `expected_fingerprint`, `confirm_install=true` ไม่รับไฟล์ พาธ `pip` arguments หรือ URL จาก Browser

เมื่อเริ่มงานจะทำตามลำดับ:

1. อ่าน Lock ที่เชื่อถือได้ใน Source และตรวจ Recipe SHA-256/Platform/ABI
2. ตรวจจำนวนไฟล์ ชื่อข้ามโฟลเดอร์ ขนาด ZIP/METADATA และตรวจ SHA-256 ขณะคัดลอก Wheel ทุกไฟล์ไปยัง Snapshot ชั่วคราว
3. สร้าง Virtual Environment ใน Staging; เรียก `uv pip install` ด้วย `--offline --no-index --no-cache --only-binary :all: --require-hashes` และ Lock ที่สร้างจาก Hash ของทุก Wheel
4. ตรวจ `uv pip check`, Environment Fingerprint และ Python ABI ก่อนสลับ
5. สลับไปพาธ Runtime จริง แล้วเรียก Python ที่พาธนั้น Import โมดูลที่เชื่อถือได้ และตรวจ Dependencies อีกครั้ง; หากไม่ผ่านจะ Rollback กลับ Environment เดิม

**ไม่ใช้เครือข่ายในขั้นติดตั้งจริง**, ไม่ดาวน์โหลดโมเดล, ไม่สั่งปิด Ollama/แอปอื่น และไม่แตะ Models/Presets/Settings การคัดลอก Snapshot ต้องใช้พื้นที่ว่างเพิ่มชั่วคราวอย่างน้อยเท่าขนาด Wheelhouse รวมถึงพื้นที่สำหรับ Runtime ใหม่

ฟีเจอร์ Phase B **ซ่อมจาก uv cache (Offline)** ยังคงอยู่เป็นตัวเลือกซ่อมจาก `uv cache` รุ่นเดิม ซึ่งไม่ใช่ Wheelhouse แบบตรวจ Hash ตาม Lock — หากต้องการติดตั้งแบบตรวจสอบให้ใช้ปุ่ม Verified Wheelhouse แทน

## การจัดเตรียมชุด Wheel (ผู้ดูแลโปรเจกต์)

ตัวอย่าง Sherpa บน Windows x64 + Python 3.11:

```powershell
# ดาวน์โหลดหรือรวบรวม Wheels ขณะมีอินเทอร์เน็ต (ขั้นจัดเตรียมเท่านั้น)
.\.venv\Scripts\python.exe -m pip download --only-binary=:all: -r scripts\engine-dependencies\sherpa.txt -d cache\temp\phasec-sherpa-candidate

# สร้าง Draft และตรวจ Dependency/Extra closure โดยไม่อนุมัติไฟล์
.\.venv\Scripts\python.exe scripts\prepare_verified_wheelhouse.py --runtime-id sherpa --source cache\temp\phasec-sherpa-candidate

# หลังตรวจ Package Source, License และไฟล์ที่ต้องรวมใน Release แล้วเท่านั้น
.\.venv\Scripts\python.exe scripts\prepare_verified_wheelhouse.py --runtime-id sherpa --source cache\temp\phasec-sherpa-candidate --publish-reviewed
```

ตัวจัดเตรียมจะไม่ดาวน์โหลดเอง ไม่แก้ Trusted Lock/Wheelhouse เดิมโดยไม่ตั้งใจ และปฏิเสธ Wheel ที่ไม่ตรง Dependency Closure หรือเป็น Wheel สำหรับ ABI/OS อื่น

สำหรับการย้ายเครื่อง ให้เก็บ **Trusted Lock + Wheels + Trusted Recipe** ครบและมี `uv` กับ Python 3.11 ที่ใช้งานได้บนเครื่องปลายทาง Windows Virtual Environment เดิมไม่ใช่สิ่งที่รับประกันว่า Portable; ให้ติดตั้ง Runtime ใหม่จากชุด Wheels ที่ตรวจแล้ว

## ผลการทดสอบบนเครื่องพัฒนา

- **Sherpa runtime:** เตรียม Wheel จริงจาก `sherpa-onnx==2.0.1`, `sherpa-onnx-core==2.0.1`, `numpy==2.2.6` ได้ 3 ไฟล์ รวม **31,744,498 bytes** และสร้าง Trusted Lock
- ทดสอบการติดตั้งจริงแบบ Offline ใน **โปรเจกต์ชั่วคราวแยกจากโปรเจกต์หลัก** สำเร็จ ตรวจ `uv pip check`, Import `sherpa_onnx` และ `numpy` ผ่านก่อนลบโปรเจกต์ทดลอง
- Runtime ที่ติดตั้งอยู่ในโปรเจกต์จริงยังไม่ถูกเปลี่ยนแปลง
- Metadata ที่ตรวจพบ: Sherpa-ONNX และ sherpa-onnx-core ระบุ Apache-2.0; NumPy ระบุเงื่อนไขลักษณะ BSD พร้อม third-party bundled components — **ยังต้องตรวจประกาศลิขสิทธิ์/การแจกจ่ายทั้งหมดก่อนทำ Release**
- Wheelhouse สำหรับ Runtime อื่น ๆ โดยเฉพาะ M2M100/Torch และ Wayu ที่มี Git/URL dependencies **ยังไม่ได้จัดเตรียม/ยืนยันว่าครบ**; UI จะรายงานว่าไม่พร้อม ไม่สร้างผลสำเร็จเทียม
- การติดตั้ง Runtime พร้อมใช้งานไม่ใช่การยืนยันว่าโมเดล M2M100 แปลจริงได้: ความจำ/Commit ของเครื่องยังเป็นข้อจำกัด

## งานถัดไป

จัด Wheelhouse แบบตรวจสิทธิ์ให้ครบ Runtime ที่อนุญาต, เพิ่ม Supply-chain provenance และการลงลายเซ็นที่เชื่อถือได้ของ Publisher, ทดสอบการย้ายโฟลเดอร์/เครื่องอื่น และสร้าง ZIP/Release แยกตัว Dependencies ตามแพลตฟอร์มเมื่อพร้อม
