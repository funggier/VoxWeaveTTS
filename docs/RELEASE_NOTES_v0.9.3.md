# VoxWeaveTTS v0.9.3 — Complete TTS Engine & English Routing Release

**วันที่เผยแพร่:** 17 พฤศจิกายน 2026 · **Windows 10/11 x64 Portable** · [คู่มือภาษาไทย](../README_TH.md) · [v0.9.2](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.9.2)

รุ่นนี้รวมความสามารถของ v0.9.2 ทั้งหมด และการพัฒนาต่อจาก 8 commits ที่ยังไม่ได้เผยแพร่: Worker Gateway แบบแยก Python Environment, ระบบจัดการหน่วยความจำ/คิวที่รักษา Worker ที่โหลดแล้ว, คำสั่ง Stop ที่ปิด Process ลูก, รองรับ Wayu Paxa Edge สำหรับการใช้งานส่วนบุคคล, และแก้ไขการเลือก Engine/Model ตามภาษาให้ **โมเดล TTS ที่พร้อมใช้ทุกตัวสามารถกำหนดเป็น English (en)** ได้

## สิ่งที่เพิ่มและแก้ไข

### 1. เลือกอ่านอังกฤษกับ Engine ทุกตัว

- ในแท็บ **โมเดลเสียงตามภาษา** เลือก **English (en)** แล้วกำหนด Engine/Model ที่ติดตั้งและพร้อมใช้งานได้ทุกตัว
- **MakHam Paradee**: ไทย/อังกฤษ ผ่าน `paradee_thai` (มีอยู่แล้วใน Portable)
- **FastThaiG2P ThaiSom**, **Vachana** และแพ็กเกจ `.vwmodel` ของทั้งสองรุ่น: ไทย/อังกฤษ
- **Wayu Paxa Edge [NC / NonCommercial]**: ไทย/อังกฤษทั้ง 12 Voice *เฉพาะกรณีผู้ใช้ติดตั้งน้ำหนักโมเดล NC แยกด้วยตนเอง*
- **MeloTTS Chinese**: จีน/อังกฤษผ่าน `zh_melo`
- **Kokoro Multilingual** และ **Supertonic 3**: รักษา Voice อังกฤษโดยเฉพาะ และ Voice ของภาษาอื่นให้ตรงตามภาษาที่เลือก
- สามารถใช้ **Engine เดียวกันและ Voice เดียวกัน** กับ Route ไทย/อังกฤษพร้อมกัน แต่เก็บ Speed, Seed, Voice Controls และ Preset แยกตามภาษาได้
- ภาษาอื่นใน Model Registry ยังคงถูกจำกัดด้วยข้อมูลความสามารถที่ประกาศไว้ ไม่ได้เปิดทุกภาษาโดยไร้การทดสอบ
- แก้ Engine contract ให้รองรับ `supported_languages` (หลายภาษาต่อ Voice) และ `voice_language_map` (แยกภาษาตาม Voice) ทั้งใน API และ External Provider ที่ได้รับอนุมัติ
- **หมายเหตุ:** สร้างไฟล์เสียงจากข้อความอังกฤษได้ ไม่เท่ากับรับรองว่าทุก Voice ออกเสียงสำเนียงอังกฤษได้ถูกต้องเท่าเสียงที่ฝึกมาเพื่ออังกฤษโดยเฉพาะ

### 2. TTS Engine Worker Gateway และการใช้ทรัพยากร

- แยกโมเดล TTS เป็น Worker ตาม Provider: `pythaitts`, `vachana`, `kokoro`, `sherpa`, `wayu-nc`; โปรโตคอล IPC ใช้ PCM16/UTF-8 โดยไม่เปลี่ยน Engine ID เดิม
- **Worker ที่โหลดโมเดลสำเร็จแล้วจะถูกเก็บไว้** เพื่ออ่านครั้งต่อไปได้เร็วขึ้น ไม่โหลดใหม่ทุกข้อความ
- หาก Windows เข้าใกล้ขีดจำกัดหน่วยความจำ จะพิจารณาปิด Worker อื่นที่ *ไม่ได้กำลังทำงาน* ก่อน; ป้องกันคิวข้อความหาย และมีการรับมือ `resource_exhausted` อย่างจำกัด
- รองรับเมนู **Install / Repair Runtime** ของ Provider; ZIP Portable นี้มีไฟล์สูตร Dependencies และสคริปต์ติดตั้งครบแล้ว; การติดตั้ง Runtime เพิ่มเติมต้องมี `uv` ใน PATH และอาจต้องเข้าถึงอินเทอร์เน็ต (ไม่ใช่การดาวน์โหลดโมเดลโดยอัตโนมัติ)
- Cache ของกระบวนการติดตั้งผ่านหน้าเว็บจัดเก็บในโฟลเดอร์ `cache/` ภายใน Portable แทนการอาศัยตำแหน่ง cache ภายนอก

### 3. คำสั่งหยุดระบบโดยไม่แตะ Ollama

- **`Stop-VoxWeaveTTS.cmd`**: หยุด Server และ Worker/Process ลูกที่ตรวจสอบแล้วว่าเป็นของการติดตั้งนี้ รวมถึง Process ที่เหลือหลังปิดหน้าต่างหลัก
- **`Stop-Console.cmd`**: ตัวเรียก Stop สำหรับ Portable; มี `-DryRun` ให้ตรวจสอบรายการก่อนปิด
- ตรวจยืนยัน Process ตาม Root, PID และเวลาเริ่ม ทำให้ไม่ฆ่า PID ที่ถูกใช้ซ้ำ หรือ Python ของโครงการอื่น
- **ไม่ปิด Ollama** และไม่ปิด Unity, Browser หรือแอปอื่นโดยอาศัยเลข Port เพียงอย่างเดียว
- ปรับ Stop ให้รับกรณี Child Process ถูกปิดไปพร้อม Parent ก่อน `taskkill` รอบถัดไป

### 4. สิทธิ์โมเดล NC / Commercial

- **น้ำหนักโมเดล Wayu Paxa Edge ภายใต้ CC BY-NC 4.0 ไม่ถูกใส่ใน Source, Portable ZIP หรือ Release assets** ผู้ใช้ต้องติดตั้งเองตามเงื่อนไขสิทธิ์ที่ใช้ได้
- Source inference ของ Wayu กับสิทธิ์ของน้ำหนักโมเดลเป็นคนละส่วน การมี Engine อยู่ในรายการไม่ได้หมายความว่า Commercial-cleared
- Model packages ที่มีสิทธิ์จำกัดหรือยังตรวจสอบไม่ครบมีเอกสาร NOTICE/LICENSE แยกไว้ และ **ไม่มีคำรับรองสิทธิ์เชิงพาณิชย์แบบครอบจักรวาล**
- **Supertonic 3: BigScience OpenRAIL-M มีเงื่อนไขเพิ่มเติม**; อื่น ๆ โปรดตรวจรายละเอียดใน `docs/COMMERCIAL_LICENSE_POLICY_TH.md` และ NOTICE ภายในแพ็กเกจ

## ชุดดาวน์โหลดครบ (9 Assets)

1. `VoxWeaveTTS-v0.9.3-portable.zip` — ตัวโปรแกรม Windows x64 พร้อม Python 3.11 Runtime, MakHam Paradee, เว็บ UI, สคริปต์ Start/Stop และเอกสาร
2. `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` — โมเดลเสริม FastThaiG2P/ThaiSom
3. `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel` — โมเดลเสริม Vachana 4 เสียง
4. `VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel` — โมเดลเสริม Kokoro (รวม Voice อังกฤษ/ญี่ปุ่น)
5. `VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel` — โมเดลเสริมจีน/อังกฤษ
6. `VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel` — โมเดลเสริม 31 ภาษา
7. `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` — โมเดลแปลภาษาแยกต่างหาก (ต้องติดตั้ง Runtime เฉพาะ)
8. `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip` — Browser Extension สำหรับ TikTok LIVE
9. `SHA256SUMS-v0.9.3.txt` — Hash SHA-256 ของไฟล์ ZIP/Model Package ทั้ง 8 รายการข้างต้น

โมเดลเสริม 5 รายการ, M2M100 และ TikTok Extension **เป็นชุดข้อมูลเดียวกับ Release v0.9.2** และตรวจ SHA-256 เทียบกับชุดเดิมเพื่อไม่แก้ไขน้ำหนักโมเดลที่ไม่เกี่ยวข้อง การอัปเดต Engine อยู่ใน Portable v0.9.3

## การติดตั้งและอัปเกรด

1. แตก `VoxWeaveTTS-v0.9.3-portable.zip` ลง **โฟลเดอร์ใหม่ที่เขียนได้บนไดรฟ์ใดก็ได้** แล้วเปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd`
2. เข้า `http://127.0.0.1:8765/` หากมีอินสแตนซ์เก่าใช้ Port 8765 อยู่ ให้ปิดอินสแตนซ์เก่าก่อน
3. สำรองข้อมูลจากรุ่นก่อนและคัดลอก **เฉพาะข้อมูลส่วนตัวที่ต้องการ**: `data/`, `presets/`, `models/packages/`, `models/ai/` และเสียงส่วนตัว *ห้ามแทน `src/`, `web/`, `runtime/python/` หรือ `.exe` ของรุ่นใหม่ด้วยของเดิม*
4. ติดตั้ง `.vwmodel` ที่ต้องการผ่าน **จัดการ Model Package**; หากต้องการ Worker แบบแยก Environment ให้มี `uv` บน PATH แล้วใช้เมนู **Install / Repair Runtime** (หรือ PowerShell `scripts/Install-EngineProvider.ps1` ตามเอกสาร)
5. ในแท็บ **โมเดลเสียงตามภาษา** กำหนด English (en) เป็นโมเดลที่ต้องการ แล้วเปิด **ใช้การเลือกโมเดลตามภาษา** ในโหมดอ่านที่ใช้; หากต้องการแยกข้อความไทย/อังกฤษภายในประโยคเดียว ให้เปิด **แยกข้อความตามภาษา** เพิ่มเติม
6. ปิดโปรแกรมและคืนหน่วยความจำอย่างเป็นระบบด้วย `Stop-VoxWeaveTTS.cmd`; ไม่ปิด Ollama

**ความเป็นส่วนตัว:** Release ไม่บรรจุ Token, Secrets, Chat history, Presets ผู้ใช้, Cache, Logs, โมเดล NC ส่วนตัว หรือ Voice Recording

## การทดสอบ

- Regression tests ของ Python และ JavaScript ทั้งโปรเจกต์ (รวม UI, กฎคิว, Worker, Language Routes และการหยุด Process)
- ทดสอบไฟล์เสียงภาษาอังกฤษบนเครื่องจริงจากโมเดลที่ติดตั้งไว้ทั้ง 9 Engine; โมเดลในกลุ่ม FastThaiG2P, Vachana และ MeloTTS ได้ทดสอบ HTTP `/v1/speech` ด้วยข้อความอังกฤษและสร้าง WAV สำเร็จ
- ทดสอบการสร้าง Portable จาก Runtime ที่ฝังมา, ติดตั้ง `.vwmodel` ชั่วคราวเพื่อใช้ทดสอบ โดยไม่แก้ไฟล์ผู้ใช้ พร้อมตรวจ ZIP และ SHA-256 ก่อนเผยแพร่
- ไม่รับรองคุณภาพสำเนียงของทุก Voice, การใช้งาน API ของแพลตฟอร์ม LIVE ระยะยาว หรือการทำงานของ Ollama Speech บนระบบ/เซิร์ฟเวอร์ทุกแบบ

เอกสารเพิ่มเติม: [ภาษาของ TTS Model](MODEL_LANGUAGE_CAPABILITIES_TH.md), [Worker Gateway](ENGINE_WORKER_GATEWAY_TH.md), [การหยุด Process](STOP_VOXWEAVETTS_TH.md), [สิทธิ์ Wayu](PERSONAL_NONCOMMERCIAL_VOICES_TH.md), [Mixed-language WAV](MIXED_LANGUAGE_TTS_TH.md), [License Policy](COMMERCIAL_LICENSE_POLICY_TH.md).
