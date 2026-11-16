# VoxWeaveTTS — TTS Engine Provider / Worker Gateway

## เป้าหมาย

VoxWeaveTTS Core รันระบบอ่านแชท กฎคำอ่าน การแปล ภาษา การจัดคิว สร้าง WAV และ Subtitle/OBS เหมือนเดิม แต่การสังเคราะห์เสียงของโมเดลสามารถแยกไปเป็น **Worker Process** ที่ใช้ Python/Dependencies ของตัวเอง ไม่ต้องใช้ Runtime ร่วมกันทั้งหมด

การเปลี่ยนนี้ **ไม่เปลี่ยน Engine ID, Voice ID, Preset, คิว หรือ API การอ่านเสียงเดิม** จึงไม่ต้องแก้การตั้งค่าที่บันทึกไว้เพียงเพราะย้าย Runtime

```text
Discord / YouTube / TikTok / Document
             |
   Rules / Translation / Routing / Queue
             |
       Engine Registry
             |
   TTS Engine Worker Gateway (stdin/stdout JSON Lines v1)
    |          |            |          |
 PyThaiTTS   Vachana      Kokoro     Sherpa / Wayu / External
   venv        venv         venv       isolated venv
    \__________|____________|__________/
             |
      PCM16 mono (8–96 kHz)
             |
    WAV / Subtitle / OBS Events
```

## โมเดลเดิมที่ย้ายแล้ว

| กลุ่ม Runtime | Engine/โมเดลเดิม | Sample rate |
|---|---|---|
| `pythaitts` | FastThaiG2P CPU, MakHam Paradee, FastThaiG2P-ThaiSom `.vwmodel` | 24,000 Hz |
| `vachana` | Vachana CPU และ Vachana Thai 4 voices `.vwmodel` | 22,050 Hz |
| `kokoro` | Kokoro Multilingual `.vwmodel` (รวมญี่ปุ่น G2P) | 24,000 Hz |
| `sherpa` | Melo Chinese, Supertonic 3 Multilingual `.vwmodel` | 44,100 Hz |
| `wayu-nc` | **[NC / NonCommercial]** Wayu Paxa Edge 12 voices | 24,000 Hz |

**Ollama Speech Adapter** ยังคงใช้ระบบเดิม (เป็นการเชื่อมต่อ Provider ภายนอก ไม่ใช่ local weights ที่จำเป็นต้องใช้ Worker Python แบบแยก) ไม่ได้ยกเลิกการใช้งานเดิม

แต่ละกลุ่มมี Python Environment ของตัวเองใต้ `runtime/engine-envs/<provider-id>/` (ignored by Git) และมีไฟล์ requirements ของกลุ่มใน `scripts/engine-dependencies/` ขณะนี้ทุกกลุ่มติดตั้ง Dependency ตามเวอร์ชันที่กำหนดและผ่านการตรวจด้วย `uv pip check`

## ติดตั้งและใช้งาน

1. เปิด **ตั้งค่า → จัดการ Model Packages → Engine Providers — Isolated Python Runtimes**
2. หากยังไม่ได้ติดตั้ง Runtime ให้กด **Install / Repair Runtime** ในกลุ่มที่ต้องการ การติดตั้งจะสร้าง Environment แยกโดยใช้ `uv` ไม่แก้ `.venv` ของโปรแกรมหลัก
3. เมื่อใช้ปุ่ม **ติดตั้ง Model Package (.vwmodel)** เหมือนเดิม โปรแกรมจะตรวจหา Provider จาก `engine_adapter` ที่อยู่ใน Manifest แล้วเริ่มติดตั้ง Runtime ที่เกี่ยวข้องอัตโนมัติในเบื้องหลัง และแสดงสถานะใน Engine Providers
4. หลัง Runtime พร้อมและมีโมเดลใน `models/` ให้เลือก Engine/Voice ในแต่ละโหมดตามเดิม ตัวโปรแกรมจะให้ Worker สร้างเสียง แล้วรวมเข้าคิวและ Subtitle ปกติ

สคริปต์ CLI:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Install-EngineProvider.ps1 -Provider all
# หรือ -Provider wayu-nc / pythaitts / vachana / kokoro / sherpa
```

ต้องมี `uv` ติดตั้งไว้เพื่อสร้าง Environment ใหม่ ในการใช้งานปกติ หลังติดตั้งเสร็จ **ไม่จำเป็นต้องให้ uv ทำงานอยู่** แต่ Worker ยังต้องใช้ Python Environment ของตน

**Portable:** Python Virtual Environment ที่สร้างด้วย venv อาจมี absolute paths บน Windows และไม่สามารถย้ายเครื่องได้อย่างสมบูรณ์ เมื่อคัดลอกโปรแกรมไปเครื่องใหม่หรือเปลี่ยนไดรฟ์ ให้สร้าง Runtime ของ Provider ใหม่ด้วยปุ่มหรือสคริปต์ด้านบน **ไม่จำเป็นต้องย้ายโมเดลหรือข้อมูลผู้ใช้กลับไปไว้ไดรฟ์ C:**

## โปรโตคอลสื่อสาร v1

ส่ง JSON บรรทัดเดียวผ่าน stdin:

```json
{"version":1,"request_id":1,"method":"synthesize","engine_id":"fastthaig2p-cpu","text":"สวัสดีครับ","voice_id":"thai_som","speed":1.0,"seed":100}
```

Wayu ใช้รูปแบบเดียวกันแต่ไม่จำเป็นต้องส่ง `engine_id` หาก Backend รองรับเพียง Engine เดียว

Worker ตอบผ่าน stdout เป็น JSON Lines:

```json
{"version":1,"request_id":1,"ok":true,"sample_rate":24000,"pcm16_b64":"..."}
```

เสียงเป็น PCM16 mono little-endian แบบ **ไม่มี WAV Header** Core ตรวจ request ID, protocol version, sample rate, ขนาดและความสมบูรณ์ของ PCM ก่อนรวมเป็น WAV และคำนวณ Timeline/Subtitles จากจำนวน Sample จริง ตัว Gateway มี timeout, จำกัดขนาดข้อมูล และสามารถเริ่ม Worker ใหม่หลังล้มเหลวได้

ข้อความ/Seed/Voice จะอยู่ใน Local IPC เท่านั้น ใช้ UTF-8 สำหรับภาษาไทย/จีน/ญี่ปุ่นโดยบังคับ `PYTHONIOENCODING=utf-8` สถานะ error ที่ส่งกลับไม่รวมข้อความแชทต้นฉบับ

## เพิ่มโมเดลใหม่โดยไม่แก้ Core

แยกสองประเภทอย่างชัดเจน:

**A. โมเดลสถาปัตยกรรมที่โปรแกรมรองรับแล้ว (.vwmodel)**

ติดตั้งไฟล์ `.vwmodel` ตามระบบเดิม (พร้อมข้อมูล SHA-256/License/NOTICE) โปรแกรมจะจับคู่ `engine_adapter` กับ Provider ที่เชื่อถือได้ สร้าง Runtime หากขาด แล้วเริ่มใช้งานได้ **โดยไม่แก้โค้ด Core และไม่ใช้ Python code จากแพ็กเกจโมเดล** ตัวโมเดลจะถูกเก็บแยกตาม Package ID/Version

**B. โมเดลสถาปัตยกรรมใหม่ (External Engine Provider)**

นักพัฒนาสร้าง Worker ของตนเองตาม JSONL Protocol v1 และวางสามไฟล์ไว้ในโฟลเดอร์:

```text
extensions/engine-providers/<provider-id>/
  provider.json       # id, engine_id, voices, sample_rate, license/capabilities
  requirements.txt    # Dependencies ของ Runtime นี้
  worker.py           # รับ JSON Lines และคืน PCM16
```

มีตัวอย่างใน `examples/tts-provider-minimal` (ใช้เสียง tone สำหรับทดสอบ Protocol ไม่ใช่โมเดล TTS)

เนื่องจาก `worker.py` และ Dependency สามารถรันโค้ดได้ **ห้ามเปิดรันอัตโนมัติจากไฟล์ .vwmodel** ผู้ใช้/นักพัฒนาต้องตรวจโค้ดให้เชื่อถือได้และอนุมัติอย่างชัดเจน:

```powershell
# 1. คัดลอก example ไปยัง extensions/engine-providers/minimal-demo
# 2. ตรวจ provider.json, worker.py และ requirements.txt ก่อนอนุมัติ
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Install-EngineProvider.ps1 -Provider minimal-demo -TrustExecutableCode
```

คำสั่งจะบันทึก SHA-256 ของไฟล์ทั้งสามลง `approved.json` ซึ่งเก็บในโฟลเดอร์ Provider เมื่อมีการเปลี่ยนเนื้อหาไฟล์โดยไม่อนุมัติใหม่ Provider จะถูกระงับการค้นพบและใช้งานโดยอัตโนมัติ หลังอนุมัติแล้วระบบจะติดตั้ง Dependencies ใน Environment แยกและลงทะเบียน Engine ผ่าน Manifest โดย **ไม่ต้องแก้ speech.py, Queue หรือ HTTP API ของ Core อีก** เมื่อหน้า Engine ได้รับการรีเฟรชจะพบรายการใหม่

การติดตั้ง External Provider เป็นการเชื่อถือโค้ดจากผู้พัฒนารายนั้นโดยตรง ต้องตรวจ License และแหล่งที่มาเอง ไม่ใช่ระบบ sandbox ด้านความปลอดภัยโดยสมบูรณ์

## สิทธิ์ใช้งาน

Wayu weights เป็น **CC BY-NC 4.0** จึงแสดง `[NC / NonCommercial]` ในชื่อโมเดลและ `commercial_status=hold` ส่วนโมเดลจากแพ็กเกจอื่นยังคง status ที่ระบุไว้ใน License Manifest การแยก Runtime ไม่เปลี่ยนสิทธิ์โมเดล การแจกจ่ายโมเดลที่มีข้อจำกัดยังต้องตรวจแยกจากการเผยแพร่โค้ด Core

## ไฟล์หลัก

- `engine_provider_catalog.py`: Provider Catalog + Provider Approval (SHA-256)
- `engine_provider_installer.py`: Provisioning + Runtime Readiness + Install Jobs
- `engine_worker_gateway.py`: IPC, WorkerSession, Restart, PCM validation
- `engine_worker_host.py`: Trusted Worker Host
- `engine_worker_legacy.py`: Legacy ONNX adapters in independent processes
- `engine_worker_proxy.py`: VoiceEngine-compatible Proxy
- `engine_worker_wayu.py`: Wayu backend
- `personal_wayu_engine.py`: Wayu descriptor/adapter without importing Torch/TLTK into the main app
