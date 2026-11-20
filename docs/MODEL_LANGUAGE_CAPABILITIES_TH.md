# การกำหนดภาษาและเลือกเสียงจาก Model Package v4

VoxWeaveTTS ใช้ข้อมูลภาษาจากไฟล์ `manifest.json` ใน Universal `.vwmodel v4` เท่านั้น ไม่อาศัยตารางความสามารถหรือ Adapter เฉพาะโมเดลที่ฝังใน Core

## Metadata ที่จำเป็น

- `package.languages` — ภาษาทั้งหมดที่แพ็กเกจประกาศว่ารองรับ เช่น `["th", "en"]`
- `engine.language` — ภาษาหลักของโมเดล หรือ `"multi"` สำหรับแพ็กเกจหลายภาษา
- `engine.voices` — รหัสและชื่อเสียงทั้งหมดของ TTS Worker
- `engine.voice_language_map` — *ตัวเลือกเพิ่มเติม* ที่ระบุว่าแต่ละเสียงออกเสียงภาษาใดได้ เช่น `{"en_s0":"en","ja_s0":"ja"}`

หากมี `engine.voice_language_map` การเลือกเสียงจะอิงภาษาของเสียงนั้นก่อนภาษาเริ่มต้น หากไม่มี แสดงว่าแพ็กเกจประกาศให้ทุกเสียงรองรับภาษาทั้งหมดใน `package.languages` ผู้สร้างแพ็กเกจต้องไม่ประกาศความสามารถเกินจริง

ตัวอย่างบางส่วนของ `manifest.json` สำหรับ TTS v4:

```json
{
  "package": {
    "id": "my-multilingual-tts",
    "version": "1.0.0",
    "title": "My Multilingual TTS",
    "kind": "tts",
    "languages": ["en", "ja"]
  },
  "engine": {
    "protocol": 1,
    "entrypoint": "plugin/worker.py",
    "operation": "synthesize",
    "language": "multi",
    "sample_rate": 24000,
    "voices": [
      {"id": "en_s0", "label": "English"},
      {"id": "ja_s0", "label": "Japanese"}
    ],
    "voice_language_map": {"en_s0": "en", "ja_s0": "ja"}
  }
}
```

ตัวอย่างนี้แสดงเฉพาะฟิลด์เกี่ยวกับภาษา; แพ็กเกจ v4 ที่ติดตั้งได้จริงต้องมี `runtime`, `rights`, `files` และ SHA-256 ตามข้อกำหนดใน [คู่มือ Universal v4](UNIVERSAL_VWMODEL_V4_TH.md)

## แนวทางสำหรับโมเดลปัจจุบัน

| โมเดล | แนวทางกำหนดภาษา |
| --- | --- |
| MakHam Paradee | เสียง `paradee_thai` รองรับ `th`, `en` ตามการประกาศในแพ็กเกจ |
| FastThaiG2P Thai Som | เสียง `thai_som` รองรับ `th`, `en` ตามการประกาศในแพ็กเกจ |
| Vachana Thai 4 Voices | เสียงไทย 4 เสียง รองรับ `th`, `en` ตามการประกาศในแพ็กเกจ |
| Wayu Paxa Edge NC | เสียง 12 เสียง รองรับ `th`, `en` ตามการประกาศ; จำกัด NonCommercial |
| Melo Chinese ONNX | เสียง `zh_melo` รองรับ `zh`, `en` ตามการประกาศ |
| Kokoro Multilingual INT8 | ต้องระบุ `engine.voice_language_map` แยกภาษาอังกฤษ/ญี่ปุ่น/ภาษาอื่นตามรหัสเสียง |
| Supertonic 3 Multilingual | ต้องระบุ `engine.voice_language_map` ให้ครบทุกรหัสเสียง เช่น `en_s0`, `ja_s1` |

Kokoro และ Supertonic 3 มีการเพิ่มเติม Metadata ภาษารายเสียงในแพ็กเกจ QA v4 โดยไม่เปลี่ยนน้ำหนักโมเดล ใช้ `scripts/qa_add_v4_voice_language_maps.py` เฉพาะเพื่อปรับข้อมูลแพ็กเกจ QA หลังตรวจ Hash แล้ว

## กฎการเลือกภาษา

เมื่อเปิดการเลือกโมเดลตามภาษา โปรแกรมจะตรวจหาภาษาในข้อความ ใช้ Engine/Model และเสียงที่ผู้ใช้กำหนดสำหรับภาษานั้น จากนั้นสร้างเสียงทีละช่วงและรวมเป็น WAV พร้อม Subtitle Timeline โดยอาศัยข้อกำหนดของ Worker Protocol v1

หากเลือกเสียงไม่ตรงภาษา โปรแกรมต้องแจ้งการตั้งค่าไม่ถูกต้อง ไม่ควรเลือกเสียงอื่นให้อัตโนมัติโดยปิดบังหรือใช้ตารางเฉพาะโมเดลจาก Core

**เรื่องสิทธิ์:** การติดตั้งแพ็กเกจโดยผู้ใช้ไม่เท่ากับอนุญาตให้ผู้พัฒนาแจกจ่ายน้ำหนักโมเดลหรือ Wheel การตรวจสิทธิ์ชุด v4 QA ทั้ง 8 ตัวยังอยู่ระหว่างดำเนินการ และไม่ควรนำไฟล์ QA ออกเป็น Public Release
