# VoxWeaveTTS v0.12.2 — Core Portable แก้ติดตั้ง Kokoro / Wayu V4

**Windows x64 Portable ZIP แบบครบชุด** · Universal `.vwmodel` **Format V4 เท่านั้น** · ติดตั้งโมเดลและ Runtime แบบออฟไลน์ · ไม่มี License Server

## แก้ไขอะไร

แก้ปัญหาที่พบใน Core v0.12.1 ซึ่งไม่สามารถติดตั้งแพ็กเกจ [Kokoro Multilingual INT8 และ Wayu Paxa Edge NC ที่เผยแพร่ไว้](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4) โดยขึ้นข้อผิดพลาด `V4PackageError: bad v4 manifest`

**สาเหตุ:** Core v0.12.1 ยอมรับนามสกุลไฟล์ใน V4 Manifest เช่น `.txt`, `.json`, `.whl` แต่ไม่อนุญาตไฟล์ซอร์ส `.tar.gz` ที่แนบเพื่อให้มี Original GPL/LGPL Corresponding Source ใน `assets/legal/source/` ของ Kokoro และ Wayu

**วิธีแก้:** Core v0.12.2 รองรับไฟล์ซอร์ส `.tar.gz` เฉพาะ **ห้าตำแหน่งที่ตรวจแล้ว** ใน `assets/legal/source/` ได้แก่ eSpeak NG 1.52.0, phonemizer 3.6.0, phonemizer-fork 3.3.2, gensim 4.4.0 และ num2words 0.5.6; ยังปฏิเสธ `.tar.gz` อื่นใน `plugin/` และ `runtime/` รวมทั้งพาธ traversal เช่นเดิม

**ไม่แก้ไขแพ็กเกจโมเดล** หรือข้อมูลเสียงใด ๆ **ไม่ลบ GPL/LGPL Source/Notice** และยังคง License ต้นทางของโมเดลทั้ง 7 ตัวไว้

## ทดสอบจริงบน Windows Portable

ทดสอบกับ **แพ็กเกจ `.vwmodel` ชุดเดียวกับที่อัปโหลดบน GitHub** และใช้ Python/uv ของ Core Portable ที่ประกอบใหม่ในโฟลเดอร์ QA แยก โดยไม่มีการติดตั้ง Dependencies ออนไลน์

| การตรวจ | ผล |
| --- | --- |
| Core v0.12.1 inspect Kokoro / Wayu | **FAIL ทั้งคู่** — `bad v4 manifest` (ยืนยันปัญหาเดิม) |
| Core v0.12.2 inspect แพ็กเกจทั้ง 7 ตัว | **PASS 7/7** |
| Kokoro ติดตั้งจริง / Runtime พร้อม | **PASS** — Wheel ติดตั้งแบบ Offline และสถานะ `ready` |
| Wayu ติดตั้งจริง / Runtime พร้อม | **PASS** — Wheel ติดตั้งแบบ Offline และสถานะ `ready` |
| Kokoro อ่านออกเสียงจริง | **PASS** — ไฟล์ WAV 24,000 Hz / 25,088 เฟรม |
| Wayu อ่านออกเสียงจริง | **PASS** — ไฟล์ WAV 24,000 Hz / 31,800 เฟรม |
| Regression Test ป้องกันการปฏิเสธไฟล์ GPL/LGPL | **PASS** — ติดตั้ง/ตรวจ SHA/ถอนติดตั้งใน Test Fixture |
| รูปแบบ v4 เท่านั้น / ไม่รวมโมเดลใน Core | **PASS** — Stage Portable ไม่มีโมเดลติดตั้งเริ่มต้น |

เพิ่มเติม: `scripts/verify_v4_core_release_model_compatibility.py` เป็น Release Gate สำหรับเทียบ **Core Portable ที่ประกอบจริง** กับโมเดลสาธารณะ 7 ตัว เพื่อไม่ให้ความต่างของเวอร์ชัน Core/แพ็กเกจทำให้ติดตั้งไม่ได้อีก

## ไฟล์ดาวน์โหลด

- **Core v0.12.2**: `VoxWeaveTTS-v0.12.2-portable.zip` — รวม Windows Launcher, Python 3.11 แบบ Portable, `uv.exe`, โค้ดโปรแกรม, Web UI, Extensions, Docs, Examples และเอกสารสิทธิ์ของ Core **ครบชุด** แต่ไม่ได้บรรจุน้ำหนักโมเดล
- **Model Packages V4 (7 ตัว)**: ดาวน์โหลดแยกจาก https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4 โดย **ใช้ไฟล์เดิมได้ทั้งหมด** ไม่ต้องดาวน์โหลดใหม่หากมีไฟล์ `.vwmodel` อยู่แล้ว
- **SHA256SUMS-v0.12.2.txt**: SHA-256 สำหรับตรวจ ZIP และสินทรัพย์เสริมของ Release นี้
- **โปรแกรมเสริม Windows SAPI v4** ที่เคยเผยแพร่ใน v0.12.1 ยังคงดาวน์โหลดได้จาก https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1 (ไม่รวมเสียง Microsoft)

## วิธีอัปเดตจาก v0.12.1

1. ปิด VoxWeaveTTS ที่รันอยู่ก่อน และสำรองโฟลเดอร์เก่าซึ่งมี Settings/Models/Presets
2. แตก `VoxWeaveTTS-v0.12.2-portable.zip` ได้โฟลเดอร์ `VoxWeaveTTS`; ใช้แยกเป็นโปรแกรมใหม่ หรือคัดลอกไฟล์ใหม่ทับโครงสร้างโปรแกรมเก่า **โดยเก็บ `data/`, `config/`, `presets/`, `models/` และ `runtime/environments-v4/` ของผู้ใช้ไว้** ห้ามลบข้อมูลที่เก็บไว้
3. เปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd` เช่นเดิม
4. เข้าเมนูจัดการโมเดล เลือกไฟล์ `VoxWeaveTTS-kokoro-multilingual-int8-1.0.0-format-v4.vwmodel` หรือ `VoxWeaveTTS-wayu-paxa-edge-nc-1.0.0-format-v4.vwmodel` ที่ดาวน์โหลดไว้ เลือกติดตั้งและยอมรับสิทธิ์
5. หลังติดตั้ง ตรวจว่า Runtime เป็น `ready` แล้วลองสร้างเสียงในโหมดอ่าน

**Portable/Relocatable:** โปรแกรมใช้ Path ภายในโฟลเดอร์ตัวเอง รองรับการย้ายโฟลเดอร์ ไม่จำเป็นต้องติดตั้งลง `C:` และไม่ใช่ตัว Installer ที่แก้ระบบ Windows

## สิทธิ์

Core ภายใต้ MIT ของ VoxWeaveTTS; โมเดล/Worker/Wheels เป็นซอฟต์แวร์ของเจ้าของต้นฉบับและใช้สิทธิ์เดิมตามเอกสาร `assets/legal/` ใน `.vwmodel` โดยเฉพาะ Wayu **CC BY-NC 4.0 (NonCommercial)** และข้อกำหนด GPL/LGPL/Corresponding Source ของ Engine ที่เกี่ยวข้อง โครงการไม่แปลงสิทธิ์บุคคลที่สามให้เป็น MIT

Vachana / `vachanatts` **ไม่ได้รวมอยู่ใน Core หรือ Release แพ็กเกจโมเดล** ยังคงอยู่เฉพาะเครื่องพัฒนาตามที่ตกลงไว้

## สำหรับนักพัฒนา: ตรวจชุด Release ก่อนเผยแพร่

~~~powershell
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_core_release_model_compatibility.py --stage dist\QA-v0.12.2\VoxWeaveTTS --packages dist\ModelPackagesV4-PublicSeven
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Portable-V4.ps1 -Version 0.12.2
~~~

ชุดตรวจนี้แยกจากการทดสอบแปลงเสียงจริง และไม่ได้เปิดเซิร์ฟเวอร์ `8765` โดยไม่จำเป็น
