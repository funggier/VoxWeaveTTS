# VoxWeaveTTS M1 — บันทึกการเชื่อม Thai Speech Engine

> สถานะ: **M1 บางส่วนใช้งานได้จริง (CPU WAV preview)**
> ตรวจสอบบน Windows 10 x64 / Python 3.11.15 / Intel Core Ultra 5 245K / Intel Graphics
> ยังไม่ใช่ Portable EXE และยังไม่มี Voice Cloning

## ที่มาของการเลือก Engine

เป้าหมาย M1 คือทำให้ระบบอ่านข้อความภาษาไทยออกเป็นเสียงจริงโดยเริ่มจากเครื่องผู้ใช้ที่ตรวจพบเพียง Intel Graphics และไม่พบเสียง Windows ภาษาไทย จึงเลือก **PyThaiTTS 1.0.0 + FastThaiG2P/Kokoro Thai ONNX** สำหรับ CPU เป็น Engine แรก แทนการพยายามให้เสียง Windows ภาษาอังกฤษอ่านไทย

แหล่งอ้างอิง:
- PyThaiTTS: https://github.com/PyThaiNLP/PyThaiTTS
- FastThaiG2P: https://github.com/awslabs/FastThaiG2P
- น้ำหนักโมเดลจาก GitHub release `awslabs/FastThaiG2P` tag `v0.3.0`: `kokoro_thai.onnx`, `thai_som.npy`, `config.json`

PyThaiTTS และ FastThaiG2P ระบุ Apache-2.0 สำหรับโค้ดตามข้อมูล Repository/Package ที่ตรวจสอบ แต่ **ยังต้องตรวจสอบเงื่อนไขการแจกจ่ายน้ำหนักโมเดลและข้อมูลฝึกแยกต่างหาก** ก่อนจัดชุด Full Portable ที่มีโมเดลรวมอยู่ ห้าม Commit น้ำหนักโมเดลหรือเสียงของผู้ใช้ขึ้น GitHub

## สิ่งที่มีจริงใน M1 ตอนนี้

- `src/voxweavetts/speech.py`: `VoiceEngine` Protocol, `FastThaiG2PEngine` Adapter, Capability Discovery, `render_wav` และการแบ่งข้อความเป็นช่วงเพื่อจำกัดภาระ CPU
- `POST /v1/speech`: รับข้อความ Rules/Pronunciations/Speed/Voice แล้วส่งเป็น `audio/wav` (24 kHz, 16-bit, mono)
- `GET /v1/engines`, `GET /v1/voices` และ `GET /v1/status` รายงานขีดความสามารถตามสภาพแวดล้อมจริง
- `speech`/ `silence` / `skip` Segments: แทนคำและสร้างเงียบจริงใน PCM (ไม่ให้โมเดลอ่าน `***`)
- UI ใน `web/index.html`: ปุ่มสร้างเสียง/เล่น/ดาวน์โหลด WAV และปรับ Speed โดยไม่ใช้ Cloud TTS
- `Start-Dev.cmd`: เลือก Python จาก `.venv` ในโฟลเดอร์โปรเจกต์ก่อน โดยตัวติดตั้งจะดาวน์โหลด Engine/Assets ไปไว้ในโปรเจกต์

**ข้อจำกัดที่สำคัญ:** มีเสียง `thai_som` แบบคงที่เพียงเสียงเดียว ไม่ใช่เสียงเจ้าของโปรเจกต์; ใช้ได้เฉพาะค่า Speed 0.6–1.5 ใน Engine ที่ติดตั้ง ไม่มี Pitch, Formant, Emotion, Voice Clone, Audio Streaming, Subtitle Playback Event หรือ OBS/Discord/YouTube Integration ในระยะนี้

## วิธีติดตั้งสำหรับทดสอบ (Developer Only)

ข้อกำหนด: `uv` (ติดตั้ง Python 3.11 ได้) + `gh` พร้อมอินเทอร์เน็ตสำหรับดาวน์โหลดโมเดลครั้งแรก ข้อมูลจะลงภายใน Root เป็นหลัก

```powershell
cd T:\Space\Projects\ProjectsProgram\VoxWeaveTTS
powershell -ExecutionPolicy Bypass -File scripts\Install-ThaiEngine.ps1
.\Test-Dev.cmd
.\Start-Dev.cmd
```

จากนั้นเปิด http://127.0.0.1:8765 ในเบราว์เซอร์และกด **สร้างเสียง WAV** ที่แผงล่าง หรือเปิด PowerShell อีกหน้าต่างแล้วรัน:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Generate-ThaiSample.ps1
```

จะได้ไฟล์ `output/api_demo.wav` ซึ่งเป็นไฟล์เฉพาะเครื่อง (ไม่ Commit)

ถ้าต้องการรันการตรวจเสียงโดยไม่ผ่าน API:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_thai_engine.py
```

ผลอยู่ที่ `output/thai_m1_smoke.wav`

## ผลตรวจสอบจากเครื่องจริง

- `fastthaig2p-cpu` ระบุ Assets พร้อมและ Runtime พร้อม
- โมเดล `kokoro_thai.onnx` มีขนาด 325,563,297 bytes; Voicepack 522,368 bytes; Config 2,516 bytes อยู่ที่ `models/fastthaig2p`
- ทดสอบสร้าง WAV จากข้อความไทยพร้อมคำอ่านและกฎเว้นเสียง 400ms ได้ไฟล์ PCM 24 kHz, Mono, 2.9s, RMS ของเสียงทั้งหมดประมาณ 2279, ผ่านการตรวจ **ไม่ใช่เสียงเงียบทั้งไฟล์**
- ทดสอบ `POST /v1/speech` ได้ไฟล์ `output/api_demo.wav` ขนาด 160,844 bytes
- Unit test ครอบคลุมการคงคำสะกดบน Subtitle, การแทนคำ, การเว้นเสียง PCM จริง, การตรวจ Engine Capability, การยืนยัน Format และ HTTP API
- **ยังไม่ได้ตรวจฟัง/ยืนยันด้วยหูว่า `อมตะ` หรือ `เซียน` ออกเสียงถูกตามต้องการ** จะต้องใช้การทดสอบคุณภาพเสียงในระยะถัดไป

## สถาปัตยกรรมเสียงและหลักการความปลอดภัย

1. `process_text` สร้าง `spoken_text` และ `display_text` แยกกัน พร้อม Segment Metadata โดยไม่ส่งคำที่ถูกกรองไป TTS
2. `render_wav` รับ Segment และใช้ Engine Adapter สร้าง signed PCM16; ช่วง Silence สร้าง Zero Samples ตาม Sample Rate
3. รวมเป็น WAV เดียวและส่งออกผ่าน API; ยังไม่มี Playback Clock, Event/Subtitle ที่ซิงก์ตามเสียงที่เล่นจริง
4. Runtime Cache อยู่ใน `cache/`, โมเดลอยู่ใน `models/`, ไฟล์เสียงอยู่ใน `output/` โดย `.gitignore` ไม่ให้เผยแพร่
5. API รับเฉพาะ loopback `127.0.0.1`, กำหนด Input สูงสุด 64 KiB, เนื้อหาความยาวไม่เกิน 8,000 ตัวอักษรใน Text API และ **500 อักขระที่อ่านจริงต่อหนึ่งงานเสียง** ในรุ่นทดลอง
6. แผนเสียงจำกัด 50 Segments และไฟล์ WAV สูงสุด 32 MB เพื่อไม่ให้บริการทดลองใช้ทรัพยากรไม่สิ้นสุด

## สิ่งที่ยังต้องทำก่อนปิด M1

- [ ] ตรวจฟังเสียงไทย (ชุดคำอ่าน `อมตะ`, `เซียน`, โทนวรรณยุกต์) และบันทึกผลด้วยวิธีที่ทำซ้ำได้
- [ ] รองรับข้อความยาวแบบคิว/ยกเลิก/อ่านทีละบท; แทนการประมวลผลในหนึ่ง HTTP request
- [ ] ปรับคำอ่านให้เป็น Native G2P/IPA Dictionary โดยแยกจากการแทนข้อความแบบตรงตัว
- [ ] ทดสอบกรณีเสียหาย/โหลดโมเดลไม่ขึ้น/ให้เครื่องทำงานยาวและความเร็วจริง
- [ ] เพิ่ม Voice Engine ที่ใช้เสียงอ้างอิงของผู้ใช้หลังตรวจ License และ Hardware
- [ ] วัดและออกแบบ API Timing สำหรับ Subtitle จากการ **เล่นเสียงจริง** ไม่ใช่การสร้างไฟล์
- [ ] ควบคุมการสร้างเสียงหลายคำขอพร้อมกัน (คิวและ cancellation) ก่อนนำไปใช้กับ Live Chat
- [ ] Build Windows Portable EXE และทดสอบเครื่องที่ไม่มี Python (M6)

## บันทึกการตัดสินใจ

เลือก CPU ONNX Engine เพื่อยืนยัน **เส้นทางสร้าง WAV ภาษาไทยจริง** ก่อน: ไม่มี GPU NVIDIA, มีจำนวนข้อมูล/โมเดลที่ต้องดาวน์โหลดไม่มาก และ Engine Adapter สามารถเปลี่ยนหรือเพิ่มได้ในอนาคต ข้อจำกัดเรื่องเสียงคงที่และภาษาพูดต้องประกาศตรงตามความจริง