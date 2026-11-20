# Engine Worker Gateway — Universal v4

VoxWeaveTTS Core เรียกใช้ Worker จาก **แพ็กเกจ .vwmodel v4 เท่านั้น** โดยไม่โหลด Adapter เฉพาะโมเดลเข้า Process หลัก

การเริ่ม Worker: ผู้ใช้ติดตั้งแพ็กเกจด้วยตนเอง → ตรวจ Manifest และ SHA-256 → สร้าง Runtime ออฟไลน์แยกตาม Dependency Fingerprint → เรียก Worker ที่มีตำแหน่งคงที่ภายในแพ็กเกจ ผ่าน JSONL (STDIN/STDOUT)

- `synthesize`: รับข้อความ/เสียงที่เลือก/ความเร็ว/seed; ส่ง PCM16 Mono Base64 พร้อม sample rate และ request ID
- `translate`: ใช้สำหรับแพ็กเกจ Translation ส่งคืนข้อความพร้อม request ID
- Log ใช้ STDERR, ไม่มีข้อความ Debug ใน STDOUT ที่เป็น JSONL
- ตรวจ Input/Output Size, Timeout, Model Readiness และความถูกต้องของ Protocol
- เมื่อถอนโมเดล Core ปิด Worker ก่อน แล้วถอน Runtime ที่ไม่มีแพ็กเกจอื่นใช้ต่อ
- ไม่ใช้ Engine ID หรือ Adapter List ที่ฝังไว้ใน Core อีก

[สัญญา Protocol และตัวอย่าง](UNIVERSAL_VWMODEL_V4_TH.md) · [โครงสร้าง Source](ARCHITECTURE.md)

**ข้อจำกัด:** Worker ภายนอกยังทำงานด้วยสิทธิ์ Windows ของผู้ใช้ ไม่มี Sandbox ป้องกันโค้ดอันตราย การกดติดตั้งคือการเลือกเชื่อถือโค้ดนั้น
