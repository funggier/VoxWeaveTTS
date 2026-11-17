# Phase D — Trusted External TTS Provider SDK และลายเซ็น Ed25519

**สถานะ:** Implemented ใน Source v0.10.0; ไม่ใช่ Plugin Store หรือการรับรองโมเดลภายนอกโดยอัตโนมัติ

## หลักการและขอบเขต

การติดตั้ง `.vwmodel v2` เป็น **ข้อมูลอย่างเดียว** (น้ำหนักเสียง/ไฟล์ config/ใบอนุญาต) ไม่สามารถระบุโค้ด Python ที่จะรันหรือสั่งติดตั้ง Dependencies ได้ External TTS Adapter เป็นแพ็กเกจโค้ดที่แยกต่างหากใน `extensions/engine-providers/<id>/` ซึ่งใช้ Worker Protocol v1 ผ่าน stdin/stdout แบบ JSON Lines และรันใน Environment ที่แยกจาก Core หลังอนุมัติแล้วเท่านั้น

Core ไม่ดาวน์โหลดกุญแจสาธารณะจากอินเทอร์เน็ต ไม่ใช้ Trust on First Use (TOFU) และไม่มี Publisher เริ่มต้นที่ไว้วางใจ กุญแจต้องมาจากช่องทางที่ผู้ใช้ตรวจสอบเอง และผู้ใช้ต้องยืนยัน **สองครั้งเป็นคนละเรื่อง**:

1. **เชื่อถือกุญแจผู้เผยแพร่:** ตรวจ SHA-256 fingerprint ของ Ed25519 Public Key จากแหล่งที่เป็นอิสระ แล้วบันทึกเฉพาะ Public Key ใน `settings/trusted-provider-publishers.json`
2. **อนุมัติให้รันโค้ด:** ตรวจลายเซ็น Ed25519 ของ `provider.json`, `worker.py`, `requirements.txt` และให้สิทธิ์ Provider ชุดนั้นโดยเฉพาะผ่าน `approved.json` แบบ v2

เพียงไฟล์ที่มีลายเซ็น **ไม่เท่ากับปลอดภัยหรือมีสิทธิ์แจกจ่าย** ลายเซ็นพิสูจน์แค่ว่าไฟล์ไม่เปลี่ยนจากชุดที่ผู้ถือ Private Key เซ็น และ Public Key ถูกตรึงให้เชื่อถือโดยผู้ใช้ ไม่ใช่การตรวจความปลอดภัยของโค้ดหรือ License ด้วยตัวเอง

ถ้าแก้ไฟล์ใดไฟล์หนึ่ง เปลี่ยนลายเซ็น เปลี่ยนกุญแจ หรือถอน Trust จะไม่แสดง Provider นั้นเป็นตัวเลือกที่ใช้งานได้อีก โปรแกรมจะตรวจสถานะใหม่ก่อนส่งงานให้ Worker; ไม่ต้องลบ Model Package โดยอัตโนมัติ

## โครงสร้าง Provider

```text
extensions/engine-providers/minimal-demo/
  provider.json           # Engine ID, Voice IDs, sample rate, license, capability
  requirements.txt        # Developer-reviewed Dependencies
  worker.py               # Worker implementation; ห้ามสั่งรันโดยอาศัย Model Package
  provider-signature.json # Detached Ed25519 signature of 3 executable inputs
  approved.json           # Local user approval; ไม่แจกใน Release
```

**วิธีเดิม:** `approved-provider-v1` ยังใช้ได้กับ Provider ที่ผู้ใช้ตรวจโค้ดและกดอนุมัติเอง โดยตรวจ SHA-256 ของทั้ง 3 ไฟล์ตลอดเวลา หากตรวจพบ `provider-signature.json` จะไม่ใช้การอนุมัติแบบเดิมเป็นทางลัด ต้องผ่านลายเซ็น v2 เท่านั้น

## วิธีทดลอง CLI

ผู้พัฒนาเก็บ Private Key **นอกโฟลเดอร์โปรแกรม/ZIP/Git** ด้วยระบบจัดการคีย์ที่เหมาะสม; เครื่องมือในโปรแกรมไม่สร้างหรือเก็บ Private Key

```powershell
# ตรวจ SHA-256 จาก Public Key ที่ผู้เผยแพร่ยืนยันผ่านช่องทางแยก
$env:PYTHONPATH='src'
python scripts/manage_signed_provider.py trust --publisher-id demo-publisher --public-key "T:\Keys\demo-public.pem" --expected-sha256 "64-hex-digits-here" --confirm-trust

# ผู้พัฒนาเซ็น 3 ไฟล์ (Private Key อยู่ภายนอก)
python scripts/manage_signed_provider.py sign --publisher-id demo-publisher --private-key "T:\Keys\demo-private.pem" --folder "extensions\engine-providers\minimal-demo"

# เครื่องผู้ใช้ตรวจลายเซ็นและตรวจสอบโค้ดก่อนอนุมัติ
python scripts/manage_signed_provider.py verify --folder "extensions\engine-providers\minimal-demo"
python scripts/manage_signed_provider.py approve --folder "extensions\engine-providers\minimal-demo" --confirm-executable-code

# ถอน Trust ของ Publisher: Provider ที่อาศัยกุญแจนี้จะใช้ไม่ได้
python scripts/manage_signed_provider.py revoke --publisher-id demo-publisher --confirm-revoke
```

เครื่องมือเหล่านี้รองรับ `cryptography` ใน **Core Python**; หากไม่มีไลบรารี ตัวตรวจลายเซ็นจะ Fail Closed โดยไม่ใช้โหมด Manual ข้ามแทน Signed Provider

## สัญญา Worker Protocol v1

ตัวอย่างที่ `examples/tts-provider-minimal/worker.py` ใช้ `voxweavetts.tts_provider_sdk.serve` ซึ่งใช้ Python Standard Library เพียงอย่างเดียว:

- Request: `version=1`, `request_id` จำนวนเต็ม, `method="synthesize"`, `text` ไม่เกิน 5,000 อักขระ, `voice_id` ที่ประกาศไว้, `speed` 0.6–5.0, `seed` 0–2³¹−1 และ `engine_id` ที่รู้จัก (ถ้าส่งมา)
- Response สำเร็จ: `version=1`, `request_id`, `ok=true`, `sample_rate`, `pcm16_b64` เป็น PCM16 mono little-endian ที่ **ไม่มี WAV header** ความยาวไม่เกิน 32 MB
- ความผิดพลาด: `ok=false` พร้อมรหัส `synthesis_failure` หรือ `resource_exhausted`, ไม่ส่งข้อความต้นทาง/Traceback/พาธภายในกลับออกไป
- SDK จำกัด Request Line 64 KiB และอ่านทิ้งส่วนเกินโดยไม่ตีความเป็นคำสั่งใหม่ ส่วน Gateway จำกัดขนาดและเวลา Response อยู่แล้ว

**ยังไม่ได้รองรับ** API STT, Voice Cloning หรือ LLM แบบ External Signed Worker ในเฟสนี้ รวมทั้งไม่มี Secure Sandbox ระดับ OS สำหรับ Python ภายนอก ผู้ใช้ที่ให้สิทธิ์รัน Code ต้องตรวจโค้ดเองก่อนทุกครั้ง

## การทดสอบ

ทดสอบ Trust/Approval แยกขั้น, Signed Payload Tamper, ลายเซ็นเปลี่ยน, การถอนกุญแจ, การปฏิเสธเมื่อไม่มี `cryptography`, ความเข้ากันได้กับ Manual Provider เดิม และการตรวจข้อความที่ไม่ใช่คำสั่ง/PCM16/Error Redaction ของ SDK; ตัวอย่าง Worker ส่งโทนเสียงเพื่อทดสอบ Protocol เท่านั้น **ไม่ใช่โมเดลสร้างเสียงพูด**
