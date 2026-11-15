# Ollama Speech — โครงสร้าง TTS Adapter แบบเลือกเปิด (Source หลัง v0.8.0)

สถานะ **Experimental / Scaffold**: ลงทะเบียน Engine ID `ollama-speech` ใน Voice Engine Registry ของ VoxWeaveTTS แล้ว แต่ค่าเริ่มต้น **ปิดและไม่พร้อมใช้งาน** ไม่มีการติดตั้ง ดาวน์โหลด หรือโหลดโมเดลโดยอัตโนมัติ และยังไม่มีหน้า UI สำหรับตั้งค่า Ollama Speech โดยตรง

## ขอบเขตและ API

- ใช้ `POST /v1/audio/speech` ของ Ollama ตาม OpenAI-compatible API ส่งเฉพาะ `model`, `voice`, `input`, `response_format=wav` (ไม่ส่ง Prompt, Tool Call หรือข้อมูลแปลภาษาเป็น JSON)
- ตรวจเมตาดาตาด้วย `GET /api/tags` และ `POST /api/show` เพื่อยืนยันว่ารายชื่อโมเดลติดตั้งอยู่และมี capability `speech`; ไม่เรียก `/api/pull`, `/api/create` หรือคำสั่ง Shell
- แปลงผล WAV เป็น PCM16 Mono 24kHz เพื่อนำไปรวมใน `render_wav` และกระบวนการ Audio Queue/Subtitle/OBS เดิมของโปรแกรม; มีข้อจำกัดความยาว/ขนาดคำตอบและตรวจชนิดเสียงก่อนนำไปใช้
- ค่า `speed` สำหรับ Ollama Speech API รุ่นนี้รองรับเพียง `1.0` เท่านั้น จึงประกาศ capability `speed=false` และปฏิเสธค่าอื่นอย่างชัดเจน; ยังไม่เปิดฟังก์ชัน Streaming ตรงไปเล่นเสียง ขณะนี้ Buffer WAV ก่อนส่งกลับ
- ใช้ Python standard library เท่านั้น ไม่มี Dependency เสริมใน Core สำหรับ Adapter นี้
- โมเดล Speech ของ Ollama ประกาศรองรับฝั่ง **Apple Silicon** ในช่วงเปิดตัวเดือนตุลาคม 2026; Windows Client สามารถเป็นส่วนที่เรียกใช้ Ollama Speech Server ที่ผู้ใช้ควบคุมและรองรับจริงบน Private LAN ได้ แต่ไม่ใช่การยืนยันว่าจะรัน Speech Inference ด้วย Ollama ใน Windows ได้ตรง ๆ
- ไม่บันเดิลน้ำหนัก/สิทธิ์เสียงจาก Ollama; การอนุญาตให้ใช้เชิงพาณิชย์ขึ้นกับโมเดลและ Voice แต่ละตัว จึงตั้งสถานะ `review_required`

## การตั้งค่าเบื้องต้น (สำหรับนักพัฒนาเท่านั้น)

ถ้ามี Ollama Server ที่รองรับ speech model และติดตั้ง `phonon` อยู่แล้ว สามารถสร้างไฟล์ `data/settings/ollama-speech.json` (อยู่ในโฟลเดอร์ของโปรแกรมแบบ Portable) ดังนี้:

```json
{
  "enabled": true,
  "base_url": "http://127.0.0.1:11434",
  "model": "phonon",
  "voice": "default",
  "language": "en"
}
```

ค่าทั้งหมดต้องผ่านการตรวจสอบ `base_url` ใช้เฉพาะ Loopback หรือ Private LAN เท่านั้น ห้าม URL สาธารณะหรือ Path/Query/Username/Password ในนั้น `model` ต้องเป็นโมเดลที่ติดตั้งจริง `voice` ต้องเป็นเสียงของโมเดลนั้นตามข้อมูลของ Ollama ควรใช้ค่า `language` ตามโมเดลที่เลือกจริง ตัวเลือก Engine ไม่พร้อมจะไม่สังเคราะห์เสียง

**เปิดใช้งานด้วยความระมัดระวัง:** ใน Windows ปัจจุบันที่ไม่ได้มี Speech Server รองรับ สามารถปล่อยค่า `enabled=false` หรือไม่สร้างไฟล์ได้เลย; จะยังใช้ MakHam, FastThaiG2P, Vachana และ Kokoro ได้เหมือนเดิม หากเซิร์ฟเวอร์รุ่นใหม่ไม่รองรับ API หรือให้ WAV ผิดชนิด โปรแกรมจะตอบข้อผิดพลาดที่แยกจากคำแปล และไม่สร้างเสียงเทียมขึ้นมา

## การทดสอบ

- `tests/test_ollama_speech.py`: ไม่มีเครือข่ายเมื่อปิด; Private URL validation; ตรวจ `/api/tags` และ `/api/show`; ตัวอย่าง WAV จริงใน Memory ผ่าน Renderer; Voice selection; malformed WAV, speed ไม่รองรับ และโมเดลไม่ติดตั้ง
- ยังไม่มีการยืนยันเสียงที่สร้างจริงจาก Phonon บน Apple Silicon หรือ Windows เพราะไม่ได้ติดตั้ง Speech Server ที่รองรับในเครื่องพัฒนาที่ทดสอบ

แหล่งอ้างอิง: [Official Ollama Speech](https://github.com/ollama/ollama/blob/main/docs/capabilities/speech.mdx), [Ollama OpenAI compatibility](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx)
