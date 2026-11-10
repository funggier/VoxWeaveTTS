# Voice Studio — Engine และค่าปรับเสียง (v0.2.0.dev4)

> สถานะ: **ใช้งานได้บางส่วน** บนเครื่อง Windows ที่ทดสอบ; ไม่ใช่ระบบ Voice Cloning/Fine-tuning  
> อ้างอิง [VOICE_TRAINING_TH.md](VOICE_TRAINING_TH.md) สำหรับงานฝึกเสียงในอนาคต

## ที่มา

ผู้ใช้ต้องการเลือก TTS Engine ที่เหมาะกับเนื้อหาภาษาไทยมากที่สุด และปรับเสียงได้ละเอียด โดยมีทั้ง **Slider และช่องตัวเลข** ใช้ปรับค่าเดียวกัน เพื่อหลีกเลี่ยงข้อจำกัดของเสียงสำเร็จรูป ปัญหาที่พบจากการอ่าน `55555` เป็น “ฮ่า” ไม่ใช่การเปลี่ยน Seed: โมเดลบางรุ่นสร้างคำไทยเพี้ยนแม้ข้อความและ G2P ถูกต้อง ดังนั้นต้องเลือก/เปรียบเทียบ Engine และทดสอบคำอ่านจริงต่างหาก

## Engine ที่ใช้งานในโครงโปรแกรม

| Engine ID | โมเดล / เสียง | สถานะ | ข้อจำกัด |
|---|---|---|---|
| `fastthaig2p-cpu` | Kokoro Thai / `thai_som` | ใช้ได้เมื่อโหลดโมเดล 325 MB + PyThaiTTS | เสียงคงที่, เสียงผู้ใช้ยังไม่ได้ |
| `makham-paradee-cpu` | MakHam Paradee INT8 ONNX / `paradee_thai` | ใช้ได้เมื่อเตรียมโมเดล 8.46 MB จาก PyThaiTTS | เสียงผู้หญิงหนึ่งเสียง, ไม่ใช่ Voice Cloning |

ทั้งสองรายการรายงานความพร้อมผ่าน `GET /v1/engines`; UI ไม่ให้เลือก Engine ที่โมเดลยังไม่พร้อม และ `GET /v1/voices` คืนเสียงที่สอดคล้องกับแต่ละ Engine รวมถึงสถานะ `ready` ไม่มี Engine จำลองที่อ้างว่าใช้สร้างเสียงได้

ข้อมูลอ้างอิง: https://github.com/PyThaiNLP/PyThaiTTS และ https://huggingface.co/pythainlp/MakHamTTS — **สิทธิ์โค้ดและสิทธิ์โมเดลต้องพิจารณาแยกกัน** ยังไม่ใส่โมเดลใน GitHub และยังไม่มี Portable ZIP; โปรดดู [Commercial-First License Policy](COMMERCIAL_LICENSE_POLICY_TH.md) สำหรับสถานะการใช้งานเชิงพาณิชย์และ Release Gate

## Control ranges (ทั้ง Slider และ Numeric Input)

| ค่า | ช่วง | ค่าเริ่มต้น | วิธีปรับ | หมายเหตุ |
|---|---|---|---|---|
| Speed | 0.60–1.50× | 1.00 | Native Engine | ปรับอัตราการพูดผ่าน Engine |
| Gain / Volume | -18 ถึง +12 dB | 0 | DSP ภายใน Python | ระวัง Clipping เมื่อเพิ่มมาก |
| Pitch | -4 ถึง +4 semitone | 0 | FFmpeg Rubber Band | อาจกระทบวรรณยุกต์ภาษาไทย |
| Bass | -12 ถึง +12 dB | 0 | FFmpeg Low-shelf | ทำให้เสียงทุ้ม/บางลง |
| Treble | -12 ถึง +12 dB | 0 | FFmpeg High-shelf | ปรับความใสของเสียง |
| Formant Preserve | On/Off | On | FFmpeg Rubber Band | ช่วยรักษา Formant เมื่อปรับ Pitch ไม่ใช่การปรับ Formant โดยอิสระ |
| Seed | 0–2147483647 | 100 | ONNX Randomness | Advanced เท่านั้น; ไม่ใช่ตัวปรับเนื้อเสียง |

`FFmpeg` เป็นเครื่องมือ DSP **เสริม** ที่จำเป็นสำหรับ Pitch/Bass/Treble. หากไม่พบ FFmpeg ตัวปรับเหล่านี้จะปิดใช้งานและ Gain/Speed ยังทำงานได้ ค่าเริ่มต้นทุกตัวเป็น 0 (Speed 1) ทำให้ PCM จากโมเดลไม่ถูกแปลงเพิ่มเติม เว้นแต่เครื่องกำหนดค่านอก Default

คำสั่ง FFmpeg ใช้ Argument List ตายตัวและเฉพาะค่าที่ Validate แล้ว ไม่ใช้ Shell Input จากข้อความผู้ใช้. ตัวโปรแกรมดูหา `runtime/ffmpeg/bin/ffmpeg.exe` ก่อนมอง PATH; **ไม่รวม FFmpeg binary ไว้ใน repo นี้** ต้องตรวจสิทธิ์ FFmpeg build และไลบรารี Rubber Band ก่อนแพ็ก Portable

## การจัดเก็บ Preset

- UI มีช่องชื่อ, ปุ่มบันทึก, รายการ Preset และปุ่มโหลดกลับ
- `GET /v1/presets` และ `POST /v1/presets` (ต้องมี `X-VoxWeaveTTS-Intent: save-voice-preset`)
- Preset เก็บ Engine ID, Voice ID, Speed, Seed, Gain, Pitch, Bass, Treble และ Formant Preserve
- เก็บไว้ใน `data/presets/voice-presets.json` แยกจากซอร์สโค้ดและไม่ขึ้น GitHub
- อัปเดต Preset ชื่อเดิมเป็นการเขียนทับเฉพาะรายการนั้น; บันทึกแบบ Atomic, จำกัด 32 Presets และตรวจชื่อก่อนเขียน

## ตัวอย่าง API

```json
{
  "text": "เซียนผู้นี้เป็นอมตะ 55555",
  "engine_id": "makham-paradee-cpu",
  "voice_id": "paradee_thai",
  "speed": 0.9,
  "voice_controls": {
    "gain_db": 2,
    "pitch_semitones": -1,
    "bass_db": 3,
    "treble_db": -1,
    "formant_preserve": true
  },
  "rules": [{"match":"555","match_mode":"five_run","spoken":"ฮ่า ฮ่า ฮ่า"}],
  "pronunciations": {"อมตะ":"อะ มะ ตะ"}
}
```

`POST /v1/speech` คืน WAV จาก Engine ที่เลือก; ตัวอย่างนี้ **ไม่ใช่การรับประกันว่าคำอ่านถูก** และยังไม่มี word timings สำหรับ Subtitle สด

## ผลทดสอบและข้อจำกัด

- ได้ WAV จริง 24kHz Mono จาก MakHam Paradee + Pitch + Gain + Bass + Treble บน CPU
- Engine ทั้งสองรองรับค่าความเร็ว Native; DSP ทำหลังสร้าง PCM ในแต่ละ Speech Segment และ **ไม่แตะ Silence Segment** เพื่อคงเวลาเงียบไว้
- ไม่มีระบบฝึกเสียงผู้ใช้, Voice Cloning, การเปลี่ยนผู้พูดอย่างอิสระ, Emotion Model, independent Formant shift, Live Chat หรือ OBS Audio Clock ในระยะนี้
- การปรับเสียงหลังสังเคราะห์ช่วยเรื่องเสียงสูงต่ำ/โทน แต่ **ไม่สามารถรับประกันแก้คำอ่าน “อมตะ”, “เซียน”, “ฮ่า” ผิด** ต้องตรวจฟังจริงและอาจต้องใช้ Engine/Phoneme Dictionary ที่ดีกว่า

## งานต่อไป

1. ทดลองเสียงของ Engine ทั้งสองกับชุดประโยคไทยรวมคำอ่านยาก สระ วรรณยุกต์ และสำนวนเกม/นิยาย
2. เพิ่มชุดเปรียบเทียบ A/B และ Preset per-Book/per-Source
3. เพิ่มโมดูล Input Voice Profile / Reference Audio / Fine-tune หลังเลือกรุ่นที่รองรับและตรวจสิทธิ์
4. ทำ Audio Timeline/Playback Clock, Queue และ Subtitle ที่เชื่อมเสียงจริง
5. ทดลอง Portable Builder และทดสอบบนเครื่อง Windows ที่ไม่มี Python