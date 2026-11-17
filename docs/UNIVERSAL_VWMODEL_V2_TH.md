# Universal .vwmodel v2 — ระบบแพ็กเกจใหม่โดยตรง

สถานะ: **Native v2 Phase A + Runtime Pool Phase B + Verified Wheelhouse Phase C — Source หลัง v0.9.5 (ยังไม่ Release)** · [คู่มือ Phase B](MANAGED_RUNTIME_POOL_TH.md) · [คู่มือ Phase C](VERIFIED_WHEELHOUSE_TH.md)

Native Universal v2 ไม่ใช่การหุ้ม Manifest v1: ติดตั้งผ่าน Model Package Manager เฉพาะ format_version = 2 และไม่ฝัง Legacy Manifest ในแพ็กเกจใหม่

## โครงสร้างหลัก

- Package — Identity, Version, ชนิดโมเดล และภาษาที่ประกาศ
- Adapter — Built-in Trusted ID / API Version; Manifest ไม่สั่ง import โค้ด
- Capabilities — Native เสียง/อัตราสุ่มสำหรับ TTS, Model Family สำหรับ Translation และ Features สำหรับชนิดอื่น
- Runtime — OS/Python ABI/Accelerator และ Recipe/Lock ข้อมูลเท่านั้น
- Assets/Rights — ไฟล์น้ำหนัก, Tokenizer, SHA-256, License, Attribution และ Provenance

จัดเก็บภายใน models/universal/v2/<kind>/<package-id>/<version>/ โดยไม่ปะปนกับโมเดล v1 เดิมในเครื่อง

## ตัวอย่างโฟลเดอร์ Native v2 TTS

    prepared-model/
      speaker_config.json
      voices/th_f_1.onnx
      manifest-assets.json
      legal/rights.json

เนื้อหา manifest-assets.json:

    {"paths": ["speaker_config.json", "voices/th_f_1.onnx"]}

ตัวอย่าง legal/rights.json (**ลิงก์และข้อมูลเป็น placeholder; ต้องแทนที่ด้วยข้อมูลที่มาจริง**):

    {
      "license": {
        "spdx": "MIT",
        "url": "https://example.org/model-license",
        "attribution": "Replace with genuine upstream attribution",
        "review_status": "review_required"
      },
      "source": {
        "url": "https://example.org/model",
        "revision": "verified-model-revision"
      }
    }

สร้าง v2-spec.json ไว้นอก prepared-model:

    {
      "package": {
        "id": "example-thai-voice",
        "version": "1.0.0",
        "kind": "tts",
        "title": "Example Thai Voice",
        "languages": ["th"]
      },
      "adapter": {
        "id": "vachana-onnx-v1",
        "api_version": 1,
        "trust": "builtin"
      },
      "runtime": {
        "id": "vachana",
        "kind": "python-venv",
        "python": "3.11",
        "platform": "windows-x64",
        "accelerator": "cpu",
        "install_policy": "reuse-only",
        "lockfile": null,
        "source": "reuse-only"
      },
      "capabilities": {
        "language": "th",
        "sample_rate": 22050,
        "voices": [
          {"id": "th_f_1", "label": "Female 1", "asset": "voices/th_f_1.onnx"}
        ]
      }
    }

ตัวอย่างคำสั่ง (ต้องเป็นน้ำหนักโมเดลที่ถูกต้องและมีสิทธิ์ใช้งาน):

    .\.venv\Scripts\python.exe scripts\build_vwmodel_v2.py --source .\prepared-model --spec .\v2-spec.json --output .\dist\ModelPackages\Example-Thai-Voice-v2.vwmodel

Builder สร้าง Manifest v2 จาก Spec และ File Hash โดยตรง ไม่ใช้ Manifest v1 และไม่รัน Python Module/Script จากโมเดล

## การรองรับใน Phase A

- Native TTS: Vachana, FastThaiG2P, Kokoro, Supertonic, Melo Chinese (ผ่าน Built-in Trusted Worker)
- Native Translation: M2M100 SafeTensors + Tokenizer
- STT / Voice Cloning / LLM: ติดตั้งข้อมูลที่ตรวจแล้วได้ แต่ไม่มี Adapter Runtime สำหรับประมวลผลจริง
- Runtime: ตรวจ Declarative reuse-only / recipe-only / bundled-wheels และ SHA ของทุกไฟล์ แต่ยังไม่ติดตั้ง Wheelhouse/Dependencies จาก ZIP
- v1 TTS / v1 AI: **ปิดเส้นทางติดตั้งใน Model Package Manager รุ่นใหม่**; จะไม่แปลงหรือโหลดเป็น v2 แบบเงียบ ๆ
- แพ็กเกจ Wayu NC ที่เป็น PyTorch serialization รุ่นเดิมยังไม่รองรับใน Native v2 เพราะต้องสร้างกลไกตรวจ Hash/Adapter เฉพาะก่อน

## ข้อกำหนดด้านความปลอดภัย

1. ตรวจ Manifest, ZIP Index, Bounded Size, SHA-256, Compression Ratio, Duplicate Names, Traversal และ Symlink ก่อนใช้
2. ไม่รับ Executable, Pickle-backed PyTorch Weight หรือ Install Hook ใน Native v2
3. ติดตั้งผ่าน Staging และ Atomic Rename; Failed Integrity Check ต้องไม่ทิ้ง Installed Package
4. Adapter ID ใน Manifest ไม่ได้ทำให้โค้ดกลายเป็น Trusted เอง — ต้องตรงกับ Allowlist ของโปรแกรม
5. Runtime/Offline Wheels ไม่ถูก Execute หรือ Install อัตโนมัติ; ต้องผ่าน Trusted Installer + User Approval ที่แยกต่างหาก
6. SHA-256 เป็นการตรวจความสมบูรณ์ ไม่ใช่การตรวจตัวตนผู้เผยแพร่; ตรวจ License Model/Dataset แยกเสมอ

**ไม่มีการลบไฟล์โมเดล v1, User Settings, Presets หรือ Ollama โดยอัตโนมัติ** แม้โค้ดตัวติดตั้งใหม่จะไม่รองรับ v1 แล้ว

## ขั้นต่อไป

Phase B — Managed Environment Pool, Runtime Fingerprint/Health Check และการซ่อม Offline หลังย้ายโฟลเดอร์: **เพิ่มใน Source แล้ว** · [คู่มือและข้อจำกัด Phase B](MANAGED_RUNTIME_POOL_TH.md)

Phase C — Verified Offline Wheelhouse พร้อม SHA-256, Consent และ Atomic Runtime Installer: **เพิ่มใน Source แล้ว** และมี Trusted Wheelhouse จริงสำหรับ Sherpa, PyThaiTTS และ M2M100; Vachana/Kokoro ยังเป็น Draft รอตรวจสิทธิ์ · [รายละเอียด](VERIFIED_WHEELHOUSE_TH.md)

Phase D — Signed External Adapter, SDK, STT/LLM/Cloning Runtime และ Stress Test / Native Model Packs สำหรับ Release

## ผลทดสอบจากไฟล์จริงในเครื่อง

- สร้างและติดตั้ง Native v2 จากโมเดลที่ตรวจสอบ Hash แล้ว: TTS 6 ชุด (MakHam, FastThaiG2P, Vachana, Kokoro, Supertonic 3, Melo Chinese) และ Translation M2M100 หนึ่งชุด
- ไฟล์แพ็กเกจอยู่ใน dist/ModelPackagesV2/ และมี SHA256SUMS.txt แยก; รุ่นในชื่อ Model อาจเป็น 1.0.0 แต่ Format เป็น 2
- MakHam สร้างเสียงจริงจาก Native v2 ได้แล้ว; M2M100 ผ่านการติดตั้งและค้นหา Runtime แต่การแปลจริงยังไม่สำเร็จเพราะ Windows Paging File ไม่พอ (OSError 1455)
- M2M100 Core ใช้ Isolated Worker เสมอ ไม่พยายามโหลด PyTorch น้ำหนัก 418M เข้าโปรเซสหลัก; ผู้ใช้ต้องปรับ RAM/Commit ด้วยตนเองหากต้องการทดสอบข้อความจริง
- การลบแพ็กเกจจะปฏิเสธเมื่อมีไฟล์อื่นเพิ่มหรือมีน้ำหนักโมเดลเปลี่ยนแปลง และ Builder ไม่เขียนทับ Archive ที่มีอยู่แล้ว

Universal v2 Phase A ไม่ใช่การรับรองว่าโมเดล v1 ทุกตัวกลับมาใช้งานได้ทันที: ต้องเตรียมน้ำหนัก/Metadata/สิทธิ์และทดสอบแพ็กเกจใหม่แต่ละสถาปัตยกรรมก่อน
