# Multilingual TTS and model packages (Windows Portable v0.8.0)

สถานะ: รวมอยู่ใน **Windows Portable Release v0.8.0**; ดาวน์โหลด `.vwmodel` แยกและติดตั้งในหน้าโปรแกรม

## ผลบนเครื่องทดสอบ

ติดตั้ง Kokoro-82M v1.0 INT8 ONNX CPU ผ่าน .vwmodel ที่ตรวจ SHA-256 ของทุกไฟล์
และลงทะเบียนเป็น `model-kokoro-multilingual-int8-1_0_0` พร้อมเสียง 18 แบบ
จำนวน 7 ภาษาหลัก: อังกฤษ (US/UK), สเปน, ฝรั่งเศส, ฮินดี, อิตาลี, ญี่ปุ่น, โปรตุเกส

- ทดลองสังเคราะห์เสียง PCM16 24 kHz สำเร็จบน CPU ด้วยข้อความ EN, FR, JA, ES, IT, HI, PT
- รูปแบบ .vwmodel มีเฉพาะ ONNX weights, voices-v1.0.bin และ legal notices ไม่มี Python/DLL/EXE
- แพ็กเกจที่สร้างในเครื่อง: `dist/ModelPackages/VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel`
- ติดตั้งแพ็กเกจไว้ที่ `models/packages/kokoro-multilingual-int8/1.0.0/`
- Dependencies: `kokoro-onnx==0.6.0`, ONNX Runtime, numpy, phonemizer, espeakng-loader
- **Japanese G2P fix:** การส่งคันจิให้ `kokoro-onnx` พร้อม `lang="ja"` ตรง ๆ ยังใช้ eSpeak และออกเสียงชื่ออักษร (`Chinese letter` / `Japanese letter`) แทนการพูดจริง ตั้งแต่ Portable v0.9.1 มี `misaki[ja]==0.8.0` + `unidic-lite==1.0.8` ติดตั้งไว้ให้แล้ว (Development Python ต้องติดตั้งเอง) และส่ง phonemes จาก `misaki.ja.JAG2P()` เข้า `Kokoro.create(..., is_phonemes=True)` สำหรับเสียง `j*` เท่านั้น เสียงอังกฤษและภาษาอื่นยังใช้เส้นทางเดิม
- สำหรับ Development: ใช้ `.venv\\Scripts\\python.exe -m pip install "misaki[ja]==0.8.0" "unidic-lite==1.0.8"` จากโฟลเดอร์โปรเจกต์; การสร้าง Portable ใหม่ต้องแนบแพ็กเกจและพจนานุกรมเหล่านี้ใน Python Runtime และทดสอบเสียงญี่ปุ่นจริง ห้ามเปลี่ยนกลับไปใช้ eSpeak ญี่ปุ่นโดยอัตโนมัติเมื่อ G2P ไม่พร้อม
- บันทึก Model SHA256: ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c
- บันทึก Voices SHA256: bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d

**ข้อจำกัด:** ภาษาไทยยังใช้ MakHam/FastThaiG2P/Vachana แยก; Kokoro v1.0 แพ็กนี้
ไม่มีจีน เกาหลี เยอรมัน หรือรัสเซียเป็น TTS Engine อย่าสับสนกับรายการภาษาของ AI Translation
ที่รองรับการแปลได้กว้างกว่า การทดสอบแยกภาษาแต่ละกระบวนการทำงานผ่าน แต่การ
สังเคราะห์หลายภาษาใน ONNX Session เดียวเคยพบ Memory Allocation Error
เมื่อ RAM เครื่องเหลือน้อย; งาน Queue ปกติสร้าง Engine ต่อ Speech Job

## การตั้งค่าอ่านเสียงตามภาษา

1. เข้าแท็บ **โมเดลเสียงตามภาษา** เพื่อกำหนด Engine / Voice แยกตามภาษาเพียงจุดเดียว
2. เลือกภาษา → TTS Engine → Voice แล้วกด **กำหนดโมเดลให้ภาษา** ภาษาที่กำหนดแล้วจะหายจากช่องเพิ่มภาษา
3. หากต้องการกำหนดภาษาเดิมใหม่ กดปุ่ม **ลบ** หน้ารายการ จากนั้นภาษาจะกลับมาในช่องเพิ่มภาษา
4. แต่ละภาษามีส่วนพับเก็บได้ **ปรับเสียง** อยู่ใต้ชื่อภาษา โดยมีตัวปรับเหมือน **ปรับเสียงและโมเดล** ได้แก่ ความเร็ว ความดัง ระดับเสียงสูง–ต่ำ เสียงทุ้ม เสียงแหลม Formant และ Seed เมื่อปรับแล้วกด **บันทึกเสียงของภาษานี้** เพื่อบันทึกเฉพาะภาษานั้น หรือใช้ **บันทึกการตั้งค่า** ด้านบนเพื่อบันทึกค่าของทุกภาษาที่กำลังแก้ไข
5. ใต้ส่วนปรับเสียงมี **Voice Presets** ใช้โฟลเดอร์ `presets/` เดียวกับทุกโหมด สามารถ **บันทึก Preset**, **ใช้ Preset**, และ **รีเฟรช Preset** ได้ การโหลด Preset จะนำมาเฉพาะค่าปรับเสียง ไม่เปลี่ยน Engine/Voice ที่เลือกให้ภาษานั้น ต้องกดบันทึกเสียงของภาษานั้นอีกครั้งเพื่อใช้งานจริง
6. กด **บันทึกการตั้งค่า** เมื่อเปลี่ยนรายการหรือกดลบ
7. เปิดโหมดที่ต้องการ เช่น สร้างเสียง อ่านเอกสาร คิว YouTube Discord หรือ TikTok แล้วเปิดหัวข้อ **กำหนดการอ่านข้อความและข้อมูลพิเศษ** จากนั้นเลือก **ใช้การเลือกโมเดลตามภาษา** ของโหมดนั้น (บันทึกอัตโนมัติ)
8. ในหัวข้อ **ปรับเสียงและโมเดล** ของแต่ละโหมด ช่อง **Default Engine / Model** กำหนดโมเดลสำรองสำหรับโหมดนั้น ซึ่งใช้เมื่อปิดการเลือกโมเดลตามภาษาหรือไม่มีภาษาตรงกับรายการที่กำหนด

ระบบอ่านอักษรของ `spoken_text` หลังผ่าน Rules และ AI Translation ก่อนเลือก Engine
แต่เป็น **Script Detection ไม่ใช่ Language Classification**: สเปน ฝรั่งเศส อิตาลี
เยอรมัน และโปรตุเกสใช้ Latin script เช่นเดียวกับอังกฤษ จึงเดาแยกจากข้อความสั้นไม่ได้
ให้เลือกภาษาปลายทางใน AI Translation หรือส่ง `language` เช่น `"fr"` ในคำขอ
`/v1/jobs` หรือ `/v1/speech` เพื่อระบุภาษาที่ต้องการ
หากเปิด AI Translation และระบุภาษาปลายทาง ระบบเลือก Engine ของภาษาปลายทางโดยตรง

API:

- `GET /v1/settings/language-routes`: รายชื่อภาษา, revision, routes (ไม่มีสวิตช์ส่วนกลาง)
- `POST /v1/settings/language-routes` + `X-VoxWeaveTTS-Intent: save-language-routes`
  Body: `{"expected_revision":0,"routes":{"th":{"engine_id":"makham-paradee-cpu","voice_id":"paradee_thai"},"fr":{"engine_id":"model-kokoro-multilingual-int8-1_0_0","voice_id":"ff_siwis","speed":1.30,"seed":100,"voice_controls":{"gain_db":0,"pitch_semitones":0,"bass_db":0,"treble_db":0,"formant_preserve":true}}}}`
- ค่าปรับ `speed`, `seed`, `voice_controls` เป็น Optional ต่อภาษา หากไม่ได้กำหนดค่าจะใช้ค่าของโหมดนั้นตามเดิม หากกำหนดจะมีลำดับความสำคัญสูงกว่าค่าปรับเสียงประจำโหมดเมื่อเลือกภาษานั้นตรง
- `GET /v1/presets` และ `POST /v1/presets` ใช้ชื่อ Preset และโฟลเดอร์ร่วมกับทุกโหมด; การใช้ Preset กับภาษาเปลี่ยนเฉพาะเสียง ไม่เปลี่ยน Engine/Voice ของภาษานั้น
- `GET /v1/engines`: Kokoro Engine ประกาศ `language="multi"` และแสดงเสียงทุกตัว
- `GET /v1/settings/mode-voices`: มี `language_routes` เป็นแผนที่ `mode → enabled` สำหรับแต่ละโหมด
- `POST /v1/settings/mode-voices` + `X-VoxWeaveTTS-Intent: save-mode-voice`: ตั้งค่า `{"expected_revision":0,"mode":"__language_route__","settings":{"source_mode":"live","enabled":true}}`
- `POST /v1/jobs` และ `/v1/speech`: ส่ง `mode` (เช่น `studio`, `live`, `reader`) เพื่อเลือกสวิตช์ของโหมดนั้น; ไม่ส่งจะถือว่าเป็น `studio` ส่วน `language` เป็นค่า optional สำหรับระบุภาษาเหนือการตรวจอัตโนมัติ

ไฟล์การกำหนดภาษาอยู่ใน `data/settings/language-voices.json` และสวิตช์แต่ละโหมดอยู่ใน `data/settings/mode-voices.json` ซึ่งใช้พาธสัมพันธ์กับตัวโปรแกรม
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
