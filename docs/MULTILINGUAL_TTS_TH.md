# Multilingual TTS and model packages (developer build)

สถานะ: พัฒนาใน Source Project หลัง release v0.7.2; **ยังไม่ได้ปล่อย Portable ZIP รุ่นใหม่**

## ผลบนเครื่องทดสอบ

ติดตั้ง Kokoro-82M v1.0 INT8 ONNX CPU ผ่าน .vwmodel ที่ตรวจ SHA-256 ของทุกไฟล์
และลงทะเบียนเป็น `model-kokoro-multilingual-int8-1_0_0` พร้อมเสียง 18 แบบ
จำนวน 7 ภาษาหลัก: อังกฤษ (US/UK), สเปน, ฝรั่งเศส, ฮินดี, อิตาลี, ญี่ปุ่น, โปรตุเกส

- ทดลองสังเคราะห์เสียง PCM16 24 kHz สำเร็จบน CPU ด้วยข้อความ EN, FR, JA, ES, IT, HI, PT
- รูปแบบ .vwmodel มีเฉพาะ ONNX weights, voices-v1.0.bin และ legal notices ไม่มี Python/DLL/EXE
- แพ็กเกจที่สร้างในเครื่อง: `dist/ModelPackages/VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel`
- ติดตั้งแพ็กเกจไว้ที่ `models/packages/kokoro-multilingual-int8/1.0.0/`
- Dependencies: `kokoro-onnx==0.6.0`, ONNX Runtime, numpy, phonemizer, espeakng-loader
- บันทึก Model SHA256: ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c
- บันทึก Voices SHA256: bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d

**ข้อจำกัด:** ภาษาไทยยังใช้ MakHam/FastThaiG2P/Vachana แยก; Kokoro v1.0 แพ็กนี้
ไม่มีจีน เกาหลี เยอรมัน หรือรัสเซียเป็น TTS Engine อย่าสับสนกับรายการภาษาของ AI Translation
ที่รองรับการแปลได้กว้างกว่า การทดสอบแยกภาษาแต่ละกระบวนการทำงานผ่าน แต่การ
สังเคราะห์หลายภาษาใน ONNX Session เดียวเคยพบ Memory Allocation Error
เมื่อ RAM เครื่องเหลือน้อย; งาน Queue ปกติสร้าง Engine ต่อ Speech Job

## การตั้งค่าอ่านเสียงตามภาษา

1. เข้า **กำหนดโมเดลเสียงตามภาษา (Multilingual TTS)** ในหน้าโปรแกรม
2. เลือกภาษา → TTS Engine → Voice แล้วกด **กำหนดโมเดลให้ภาษา**
3. เพิ่มหลายภาษาได้โดยไม่ต้องเปลี่ยน Engine ของโหมด Studio / Reader / Live
4. ติ๊ก **เปิดการเลือกโมเดลตามภาษา (ทุกโหมด)** และกด **บันทึกการตั้งค่า**
5. หากภาษาหนึ่งยังไม่ได้กำหนด จะใช้ Engine ที่เลือกไว้ในโหมดนั้นตามปกติ

ระบบอ่านอักษรของ `spoken_text` หลังผ่าน Rules และ AI Translation ก่อนเลือก Engine
แต่เป็น **Script Detection ไม่ใช่ Language Classification**: สเปน ฝรั่งเศส อิตาลี
เยอรมัน และโปรตุเกสใช้ Latin script เช่นเดียวกับอังกฤษ จึงเดาแยกจากข้อความสั้นไม่ได้
ให้เลือกภาษาปลายทางใน AI Translation หรือส่ง `language` เช่น `"fr"` ในคำขอ
`/v1/jobs` หรือ `/v1/speech` เพื่อระบุภาษาที่ต้องการ
หากเปิด AI Translation และระบุภาษาปลายทาง ระบบเลือก Engine ของภาษาปลายทางโดยตรง

API:

- `GET /v1/settings/language-routes`: รายชื่อภาษา, revision, enabled, routes
- `POST /v1/settings/language-routes` + `X-VoxWeaveTTS-Intent: save-language-routes`
  Body: `{"expected_revision":0,"enabled":true,"routes":{"th":{"engine_id":"makham-paradee-cpu","voice_id":"paradee_thai"},"fr":{"engine_id":"model-kokoro-multilingual-int8-1_0_0","voice_id":"ff_siwis"}}}`
- `GET /v1/engines`: Kokoro Engine ประกาศ `language="multi"` และแสดงเสียงทุกตัว
- `POST /v1/jobs`: ยังคงรูปแบบเดิม; `language` (optional) จะใช้ระบุภาษาเหนือการตรวจอัตโนมัติเมื่อเปิด Routing

ไฟล์ตั้งค่าอยู่ใน `data/settings/language-voices.json` ใช้พาธสัมพันธ์กับตัวโปรแกรม
และตรวจ revision ก่อนแก้ไขเพื่อป้องกันหน้าเว็บหลายแท็บเขียนทับกัน

## ติดตั้งและถอนโมเดล

- **TTS Model Packages**: ปุ่มติดตั้ง `.vwmodel`, รายการ Engine/Voice และปุ่มถอนแยกแต่ละ Version
- **AI / Translation Model Packages** ใน Settings: ปุ่มติดตั้ง `.vwmodel`,
  เลือกโมเดล และปุ่มถอนแต่ละ Package
- **M2M100 รุ่นเก่า** ที่อยู่ใน `models/ai/m2m100_418m/`: มีปุ่มถอนจากหน้า Settings
  โดยตรง ไม่จำเป็นต้องแปลงเป็น `.vwmodel` ก่อน การถอนต้องยืนยันในหน้าเว็บ
  และลบเฉพาะโฟลเดอร์ที่รู้จัก/ไม่มีไฟล์แปลกปลอม ไม่รับพาธการลบจาก Browser
- การถอนโมเดลไม่มีผลกับโมเดลอื่น แต่ Voice Route ที่อ้างอิงโมเดลที่ถอนไป
  จะไม่พร้อมใช้จนกว่าจะติดตั้งใหม่หรือแก้การกำหนด

## การแจกจ่ายและสิทธิ์

Kokoro-82M ต้นทางประกาศ Apache-2.0:
https://huggingface.co/hexgrad/Kokoro-82M
ONNX conversion: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1
แนบ legal/license.txt และ legal/attribution.md ใน .vwmodel แล้ว
ยังคง `review_required` จนกว่าจะตรวจสิทธิ์ข้อมูลเสียง/การใช้เสียงและ Runtime
อย่างครบถ้วน ห้ามประกาศว่า Commercial-Cleared โดยอัตโนมัติ

ก่อน Release Portable ใหม่ ควรทำ Build-Portable และ Smoke Test บน ZIP ที่แตกแล้ว
เพื่อยืนยัน `kokoro-onnx` + `espeakng-loader` อยู่ใน Python Runtime พกพาจริง
ไม่ต้องติดตั้งโมเดลใน ZIP หลัก เนื่องจากมีแพ็กเกจ .vwmodel แยกได้
