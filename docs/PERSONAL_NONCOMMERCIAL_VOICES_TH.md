# [NC / NonCommercial] Wayu Paxa Edge — ไทย/อังกฤษ 12 เสียง

**ตั้งค่าการอ่านข้อความตามภาษา:** Wayu ทุกเสียงรองรับทั้งภาษาไทย (`th`) และภาษาอังกฤษ (`en`) เปิดแท็บ **โมเดลเสียงตามภาษา** เพื่อกำหนดให้ทั้งสองภาษาพูดด้วย Wayu รุ่นนี้ได้พร้อมกัน แม้เป็นเสียงเดียวกัน โดยใช้ Preset/Voice Controls แยกตามภาษา ไม่ต้องติดตั้งโมเดลสองครั้ง ดู [คู่มือเลือกเสียงตามภาษา](MODEL_LANGUAGE_CAPABILITIES_TH.md)

## สถานะโมเดลและสิทธิ์

โมเดล Wayu-Paxa-TTS-Edge เป็น **fixed-voice Thai/English TTS** ใช้สำหรับอ่านข้อความและคอมเมนต์ฟังส่วนตัวตามเงื่อนไขผู้เผยแพร่ มีเสียงหญิง/ชายให้เลือก 12 เสียง แต่ไม่มีคำสั่งควบคุมอารมณ์แบบ text prompt โดยตรง

- Inference source: [wayu-research/wayu-tts-inference](https://github.com/wayu-research/wayu-tts-inference), Apache-2.0, pinned revision `07ab898d516649313926f0b843b809a962f993ad`
- **Weights + Voice Styles:** [wayu-ai/wayu-paxa-tts-edge](https://huggingface.co/wayu-ai/wayu-paxa-tts-edge), **CC BY-NC 4.0**, pinned revision `8196688df56a8d08ccfa186505343adff412ab6b`
- SHA-256 `model.pth`: `eb26ac6f7da4c651389b28793d0ab59be8fa7e3e7cc5d350278b2a8d0a4d7370`
- สถานะในโปรแกรม: `[NC / NonCommercial]`, `commercial_status=hold`; ไม่ใช่ Commercial-Cleared และไม่ได้รับรองสิทธิ์เสียง/ข้อมูลฝึกโดยอิสระ

**ไม่รวมไฟล์น้ำหนัก NC ใน GitHub หรือ Portable ZIP หลัก** ไม่ให้เผลอเปลี่ยน License จาก Apache-2.0 ของโค้ดไปเป็น License ของน้ำหนักโมเดล

## วิธีติดตั้ง

VoxWeaveTTS ใช้ **TTS Worker Gateway** แทนการ Import Wayu/Torch/TLTK ใน Python ของโปรแกรมหลัก ติดตั้ง Environment แยกในโฟลเดอร์ `runtime/engine-envs/wayu-nc` โดยไม่เปลี่ยน `.venv` ของโปรแกรมอื่น

จากหน้า **ตั้งค่า → จัดการ Model Packages → Engine Providers** กด **Install / Repair Runtime** ที่ `wayu-nc` หรือใช้ PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Install-WayuWorker.ps1
```

สำหรับการติดตั้งไฟล์น้ำหนักโมเดล NC (หลังอ่าน License ต้นทางและยอมรับข้อกำหนดแล้ว) ใช้:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Install-WayuWorker.ps1 -DownloadModel
```

ดาวน์โหลดแยกใน `models/personal/wayu-paxa-tts-edge/` มี `config.json`, `model.pth` และ `voices/*.pt` รวม 12 เสียง

เมื่อมีทั้ง Runtime และน้ำหนักพร้อม จะเห็น Engine ชื่อ **[NC / NonCommercial] Wayu Paxa Edge — ไทย/อังกฤษ 12 เสียง** เลือกเสียงตามความเหมาะสมกับการอ่าน เช่น `f_teen_bright`, `f_young_warm`, `m_teen_bright`, `m_mid_warm` แล้วเลือกใช้งานกับ YouTube LIVE/Document/Discord/TikTok ได้เหมือนโมเดลอื่น

### Dependency ของ Wayu

สคริปต์ใช้ชุดเวอร์ชันที่ตรวจสอบแล้วใน `scripts/engine-dependencies/wayu-nc.txt` ได้แก่ NumPy 1.26.4, scikit-learn 1.2.2, Torch 2.8.0, Transformers 4.57.6 และ TLTK 1.11 โดยแยกจาก Kokoro ONNX ที่ต้องการ NumPy 2.x

Environment นี้ผ่าน `uv pip check` และมีระบบ IPC UTF-8/PCM16 เพื่อรับส่งกับ VoxWeaveTTS Core โดยไม่ต้องแก้โมเดลเก่า

**หมายเหตุ Portable:** เมื่อติดตั้งบนเครื่องใหม่หรือย้ายโฟลเดอร์ข้ามไดรฟ์ ให้สร้าง Virtual Environment ของ Worker ใหม่ในตำแหน่งโฟลเดอร์นั้น เพราะ Python venv อาจมีพาธแบบ Absolute สำหรับ Interpreter

สำหรับสถาปัตยกรรมและการเพิ่มโมเดลใหม่ ดู [TTS Worker Gateway](ENGINE_WORKER_GATEWAY_TH.md)
