# VoxWeaveTTS — จีน เกาหลี และระบบเสียงหลายภาษา (Local CPU / ONNX)

สถานะ: **รวมใน Windows Portable v0.9.1 และไฟล์โมเดลเสริมบน GitHub Release เดียวกัน** ยังไม่ได้รับรองสิทธิ์ทุกองค์ประกอบสำหรับการใช้เชิงพาณิชย์หรือความแม่นยำของทั้ง 31 ภาษา

## โมเดลและเสียง

| ภาษา | Engine/Adapter | Voice ตัวอย่าง | Sample Rate |
|---|---|---|---|
| จีนกลาง (中文, zh) | MeloTTS Chinese ONNX ผ่าน sherpa-onnx | `zh_melo` | 44,100 Hz |
| เกาหลี (한국어, ko) | Supertonic 3 INT8 ONNX ผ่าน sherpa-onnx | `ko_s0`, `ko_s1` | 44,100 Hz |
| ญี่ปุ่น (ja) | Kokoro 82M + Misaki Japanese G2P (เดิม) หรือ Supertonic 3 | `jf_nezumi` หรือ `ja_s0` | 24,000 / 44,100 Hz |
| อังกฤษ (en) | Kokoro 82M (เดิม) หรือ Supertonic 3 | `af_heart` หรือ `en_s0` | 24,000 / 44,100 Hz |

Supertonic 3 รองรับ 31 ภาษา: อาหรับ (ar), บัลแกเรีย (bg), โครเอเชีย (hr), เช็ก (cs), เดนมาร์ก (da), ดัตช์ (nl), อังกฤษ (en), เอสโตเนีย (et), ฟินแลนด์ (fi), ฝรั่งเศส (fr), เยอรมัน (de), กรีก (el), ฮินดี (hi), ฮังการี (hu), อินโดนีเซีย (id), อิตาลี (it), ญี่ปุ่น (ja), เกาหลี (ko), ลัตเวีย (lv), ลิทัวเนีย (lt), โปแลนด์ (pl), โปรตุเกส (pt), โรมาเนีย (ro), รัสเซีย (ru), สโลวัก (sk), สโลวีเนีย (sl), สเปน (es), สวีเดน (sv), ตุรกี (tr), ยูเครน (uk), เวียดนาม (vi).

เพื่อคง ABI ปัจจุบันที่จำกัด 64 เสียงต่อ Engine ในแพ็กเกจ Supertonic นี้จึงลงทะเบียน 2 ตัวเลือก (speaker 0 และ 1) ต่อภาษา = 62 เสียง โมเดลต้นทางมี 10 speaker identities สามารถขยายรูปแบบ Voice ID ในเวอร์ชันหลังโดยไม่แก้ไฟล์น้ำหนักโมเดล

## การใช้งาน

1. ใช้ Portable v0.9.1 ที่บันเดิล `sherpa-onnx==2.0.1` หรือ Development Python `.venv` ที่ติดตั้งแพ็กเกจนี้แล้ว
2. ในหน้า **โมเดลเสียง** ติดตั้งไฟล์ `.vwmodel` สองไฟล์จาก `dist/ModelPackages/` ผ่านหน้าโปรแกรม
3. ในแท็บ **โมเดลเสียงตามภาษา** เลือก `中文 (zh) → MeloTTS Chinese / zh_melo` และ `한국어 (ko) → Supertonic 3 / ko_s0` แล้วบันทึก
4. เปิด **ใช้การเลือกโมเดลตามภาษา** สำหรับแต่ละโหมดที่ต้องการอ่าน เช่น YouTube LIVE (Browser), Discord หรืออ่านเอกสาร
5. เมื่อข้อความเป็นจีนกลางหรือเกาหลีที่ตรวจจับได้ ระบบจะเลือก Voice ตามภาษาที่กำหนดโดยไม่แปลเป็นไทย การแปลจะเกิดก่อนการเลือกเสียงก็ต่อเมื่อเปิดใช้และกำหนดการแปลไว้ตาม Settings

**กรณีข้อความผสมหลายภาษา:** ปัจจุบันการเลือกภาษาอัตโนมัติทำงานระดับข้อความ/ประโยค ไม่ใช่จัดเสียงแยกสำหรับแต่ละคำ การที่ชื่อผู้ส่งอยู่ในประโยคเดียวกับข้อความ หรือภาษาที่ใช้ตัวอักษรเดียวกัน (เช่น อังกฤษ/เยอรมัน/สเปน และ รัสเซีย/ยูเครน/บัลแกเรีย) อาจทำให้ระบบตรวจผิดได้ ให้กำหนด `language` แบบ explicit ผ่าน API หรือแยกข้อความเป็นช่วง ก่อนเลือก Engine ตามภาษานั้น การเพิ่มรายชื่อภาษาของ TTS ไม่ได้ทำให้ระบบ AI Translation รองรับภาษาใหม่เหล่านี้โดยอัตโนมัติ

## เสียงหัวเราะ `555` และกฎหลังแปลภาษา

เมื่อเปิด AI Translation เป็นจีน (zh), ข้อความต้นฉบับเช่น `ชายหนุ่มกลายเป็นอมตะ และพูดคำต้องห้าม ก่อนหัวเราะ 555` อาจแปลเป็นจีนแต่เก็บ `555` ไว้ตามเดิม กฎ `five_run` เดิมมี `spoken: ฮ่า ฮ่า ฮ่า` ซึ่งไม่ใช่อักขระจีน; ก่อนแก้ MeloTTS จึงรายงานว่าไม่รู้จักตัวอักษรและสร้างเสียงล้มเหลว แม้ Seed จะเป็น 100 ก็ตาม

ตอนนี้ระบบทำตามลำดับที่กำหนด: กฎเฉพาะโหมด → กฎร่วมก่อนแปล → AI Translation → **ตรวจภาษาข้อความที่จะสังเคราะห์และเลือกคำอ่านกฎหลังแปลตามภาษา** → โมเดล TTS เช่น zh: `哈哈哈`, ja: `ははは`, ko: `하하하`, en: `ha ha ha` และ th: `ฮ่า ฮ่า ฮ่า`. ยังคงแสดง `555` ใน Subtitle ไม่แสดงคำอ่านแทนโดยอัตโนมัติ และไม่แก้การแทนคำแบบกำหนดเองที่ไม่ได้เป็น `five_run` Thai laughter

สำหรับการปรับเอง เพิ่ม `spoken_by_language` ใน JSON Rules เช่น:

```json
{"match":"555","match_mode":"five_run","mode":"replace","stage":"post_ai","spoken":"ฮ่า ฮ่า ฮ่า","spoken_by_language":{"zh":"哈哈哈","ja":"ははは","ko":"하하하","en":"ha ha ha"}}
```

หากเปิดใช้หลายภาษา โปรดหลีกเลี่ยงการกำหนดคำอ่านภาษาไทยให้กฎทั่วไปที่ทำงานหลังแปลโดยไม่มีรูปแบบเสียงที่เหมาะกับภาษาเป้าหมาย ระบบจะไม่แปลทุกคำอ่านตามภาษาด้วยตัวเอง นอกจากนี้ กฎซ่อนคำไทยที่ทำงานหลังแปลจะไม่ตรวจพบคำที่ถูกแปลเป็นจีนแล้ว ต้องเลือกขั้นตอนกรองให้เหมาะกับความต้องการ

## Runtime / ไฟล์โมเดล

- Engine: `src/voxweavetts/sherpa_voice_engine.py` — Trusted Adapter เท่านั้น ไม่มีการรันโค้ดหรือดาวน์โหลดโมเดลจากไฟล์ .vwmodel
- Per-voice routing: `src/voxweavetts/language_routes.py`, `src/voxweavetts/engine_contract.py`, `web/language_routes.js`
- ความละเอียด PCM: signed 16-bit mono WAV, Sample Rate 44,100 Hz ตามผลที่โมเดลสร้างจริง
- สร้าง `.vwmodel` จากไฟล์ upstream ที่ตรวจสอบแล้วใน `cache/downloads/expanded/` โดยใช้ `scripts/create_multilingual_model_packs.py`
- ตรวจสอบแพ็กเกจด้วย manifest ที่มีขนาดไฟล์และ SHA-256, ติดตั้ง/ถอนผ่านระบบ Model Packages ปกติ
- ตรวจสอบ Runtime Portable ด้วย `scripts/verify_portable_multilingual.py` ซึ่งติดตั้งแพ็กเกจในโฟลเดอร์ชั่วคราวและสร้าง WAV ทั้งจีนและเกาหลี โดยไม่เปลี่ยน settings ของผู้ใช้

## สิทธิ์และแหล่งที่มา

- **MeloTTS Chinese:** ต้นทาง [MyShell.ai](https://huggingface.co/myshell-ai/MeloTTS-Chinese) ระบุ MIT License ใน Model Card, ONNX conversion จาก [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). ยังต้องตรวจสอบสิทธิ์ข้อมูลฝึกและเสียงเพิ่มเติม
- **Supertonic 3:** [Supertone](https://huggingface.co/Supertone/supertonic-3) ระบุ **BigScience OpenRAIL-M**, มีข้อจำกัดการใช้งานตามใบอนุญาต ซึ่งไม่ใช่ MIT และไม่ควรถือว่าเป็น Free-for-any-purpose; แพ็กเกจแนบใบอนุญาตฉบับเต็มและ attribution
- sherpa-onnx Runtime เป็น Apache-2.0. ไม่ใช้ Korean Piper KSS ที่ MODEL_CARD ระบุข้อมูลฝึก CC BY-NC-SA 4.0
- ทุกแพ็กใหม่ตั้ง `review_status=review_required`; ไม่ประกาศเป็น Commercial-Cleared

## ผลทดสอบสำหรับการพัฒนา

- MeloTTS Chinese: สร้าง PCM/WAV ตัวอย่าง `你好，欢迎来到我们的直播间。` สำเร็จบน CPU
- Supertonic 3 Korean: สร้าง PCM/WAV ตัวอย่าง `안녕하세요. 오늘 날씨가 좋아요.` สำเร็จบน CPU
- ผ่านการเลือก Engine/Voice แยกภาษาและการทำงานของ shared render_wav; ตรวจลำดับภาษา explicit แยกเพื่อไม่ให้ค่า Language ค้างข้ามการสร้างเสียง
- ต้องทดสอบเสียงพูดจริงต่อใน YouTube LIVE / Discord รวมถึงความเร็วกับข้อความสดยาว ๆ ก่อนเรียกว่า Production-Ready
