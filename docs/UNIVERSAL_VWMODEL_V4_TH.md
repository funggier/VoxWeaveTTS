# Universal .vwmodel v4 — Engine Plugin ของ VoxWeaveTTS

เป้าหมายคือให้ผู้ใช้ **กดติดตั้ง → เลือก .vwmodel จากเครื่อง → โปรแกรมติดตั้งโมเดลพร้อม Runtime ออฟไลน์ → Engine ปรากฏในรายการ** โดยไม่ต้องอัปเดต VoxWeaveTTS เมื่อโมเดลใหม่ทำตาม Worker Protocol v1

ไม่มีหน้าต่างยืนยันสิทธิ์ซ้ำ ไม่มี License Server และไม่มีการดาวน์โหลด Dependencies ขณะติดตั้ง

## ผู้ใช้ยอมรับอะไรเมื่อกดติดตั้ง

การกดติดตั้งถือเป็นการยอมรับเงื่อนไขของแพ็กเกจและเลือกเชื่อถือโค้ด Engine Plugin ที่อยู่ภายใน **โค้ดภายนอกยังมีสิทธิ์ตามผู้ใช้ Windows**: กระบวนการแยกไม่ได้เท่ากับ Sandbox หรือรับประกันความปลอดภัย SHA-256 ตรวจได้เพียงความครบถ้วนของไฟล์เทียบกับ Manifest ไม่ได้พิสูจน์ตัวผู้เผยแพร่

## สภาพแวดล้อมที่รองรับ

| runtime.python | ภายในแพ็กเกจ | เมื่อใช้งาน |
| --- | --- | --- |
| 3.11 | plugin/worker.py และ Wheel ทั้งชุดใน runtime/wheels/ | ใช้ Python 3.11 Portable ของ Core; ติดตั้ง Wheel ลง Runtime แยกผ่าน uv แบบ Offline |
| native | plugin/worker.exe พร้อม Libraries ของ Engine เอง | เปิด Native Worker เป็น Child Process ผ่าน Protocol โดยไม่ใช้ Python ของ Core |

Engine ใหม่ที่ใช้ Python 3.12/3.13, C++, .NET หรือ Framework อื่นสามารถบรรจุเป็น **Native Worker แบบ Self-contained EXE** ได้ แต่การติดตั้ง Python 3.12 Wheel โดยตรงยังไม่รองรับในรูปแบบ Python Wheel ของ v4 รุ่นแรก (ใช้ 3.11 เท่านั้น)

Runtime ใช้ Content Fingerprint; ชุด Wheel เหมือนกันสามารถแชร์ Runtime ได้ และ Path อ้างอิงตำแหน่งโฟลเดอร์ปัจจุบันเพื่อรองรับ Portable/Relocatable

## โครงสร้างแพ็กเกจ

~~~text
MyEngine.vwmodel
  manifest.json            # ไฟล์แรกของ ZIP, SHA-256 ทุกไฟล์
  plugin/
    worker.py              # หรือ worker.exe
    helpers.py             # โค้ดประกอบ
  assets/
    model.onnx
    config.json
  runtime/
    wheels/
      numpy-...whl
      onnxruntime-...whl
~~~

นักพัฒนาเตรียม spec.json และไฟล์ใน Source Folder แล้วใช้ Builder สร้าง Manifest + ZIP โดยอัตโนมัติ

~~~json
{
  "package": {
    "id": "my-thai-tts", "version": "1.0.0",
    "kind": "tts", "title": "My Thai TTS", "languages": ["th"]
  },
  "engine": {
    "protocol": 1, "entrypoint": "plugin/worker.py",
    "language": "th", "sample_rate": 24000,
    "voices": [{"id": "thai_voice", "label": "Thai Voice"}]
  },
  "runtime": {
    "python": "3.11", "platform": "windows-x64", "wheels": []
  },
  "rights": {
    "spdx": "MIT",
    "url": "https://opensource.org/license/mit",
    "attribution": "ตัวอย่างเท่านั้น — เปลี่ยนเป็นสิทธิ์ของโมเดลจริง",
    "source": "https://github.com/funggier/VoxWeaveTTS"
  }
}
~~~

สำหรับ Worker Native ให้เปลี่ยน entrypoint เป็น plugin/worker.exe, runtime.python เป็น native และ wheels เป็นรายการว่าง

## Worker Protocol v1

Child Process รับ JSON Lines ผ่าน STDIN และส่ง JSON Lines ผ่าน STDOUT (ส่ง Log ไป STDERR) โดยได้อาร์กิวเมนต์ --model-dir ที่ Core คำนวณจากโฟลเดอร์ติดตั้งปัจจุบัน ห้ามฝัง Absolute Path ไว้ใน Runtime

~~~json
{"version":1,"request_id":1,"method":"synthesize","text":"สวัสดีครับ","voice_id":"thai_voice","speed":1.0,"seed":123,"engine_id":"model-my-thai-tts-1_0_0"}
~~~

ผลลัพธ์ต้องเป็น PCM16 Mono Little-endian ที่เข้ารหัส Base64 พร้อม sample_rate ตรงกับ Manifest

~~~json
{"version":1,"request_id":1,"ok":true,"sample_rate":24000,"pcm16_b64":"..."}
~~~

เมื่อไม่สำเร็จให้คืนค่า:

~~~json
{"version":1,"request_id":1,"ok":false,"error":"synthesis_failure"}
~~~

Core ตรวจ request_id, protocol version, sample rate, PCM size และ timeout เสียงนำไปใช้กับคิวอ่าน, Voice Controls, API และ Subtitle Timeline เดิมได้ทันที

## Translation Worker ใน v4

แพ็กเกจชนิด translation ใช้ Worker แบบเดียวกัน แต่มี operation=translate แทนการสร้างเสียง และไม่มี sample_rate หรือ voices

~~~json
{
  "package": {"id": "my-translator", "version": "1.0.0",
              "kind": "translation", "title": "My Translator",
              "languages": ["en", "th"]},
  "engine": {"protocol": 1, "entrypoint": "plugin/worker.py",
             "operation": "translate", "languages": ["en", "th"]},
  "runtime": {"python": "3.11", "platform": "windows-x64",
              "wheels": []},
  "rights": {"spdx": "MIT", "url": "https://opensource.org/license/mit",
             "attribution": "Replace with actual model rights",
             "source": "https://github.com/funggier/VoxWeaveTTS"}
}
~~~

คำขอ Translation:

~~~json
{"version":1,"request_id":1,"method":"translate","text":"Good morning.","model":"my-translator@1.0.0","source_language":"en","target_language":"th"}
~~~

ตอบกลับ:
~~~json
{"version":1,"request_id":1,"ok":true,"text":"สวัสดีตอนเช้า"}
~~~

ตัวอย่าง Worker อยู่ใน examples/v4-translation-plugin/plugin/worker.py ส่วน M2M100 เป็นตัวอย่างโมเดลแปลภาษาจริงที่มี Wheel และ Safetensors ของตัวเอง โค้ด Worker ไม่ต้อง Import โมดูลของ Core

## ตัวอย่างสร้างแพ็กเกจ

~~~powershell
.\.venv\Scripts\python.exe -X utf8 scripts\build_vwmodel_v4.py --source examples\v4-demo-tone --spec examples\v4-demo-tone\spec.json --output cache\demo-tone-format-v4.vwmodel
~~~

ดูตัวอย่าง v4 ทั้งหมดใน examples/README_TH.md รวม Python แบบไม่มี Wheel, Python มี Wheel ใหม่, Native C#, TTS Model Worker และ Translation Worker

ตัวอย่างเหล่านี้สร้าง **เสียงโทนสำหรับทดสอบ ไม่ใช่ TTS ที่พูดจริง** ใช้พิสูจน์ว่าติดตั้ง Engine ใหม่ได้โดยไม่ต้องอัปเดต Core

## ข้อกำหนดการติดตั้ง

1. เลือกไฟล์จาก Native File Picker โดยผู้ใช้เองเท่านั้น HTTP API ไม่รับ Arbitrary Path จากข้อความภายนอก
2. ตรวจ ZIP, SHA-256, ซ้ำชื่อไฟล์, การ Traversal, Symlink, Size, Compression Ratio ก่อนติดตั้ง
3. ตรวจ Wheel Startup Hooks และ .pth ก่อนใช้ ตัวติดตั้ง uv ใช้ --offline --no-index ไม่มี Online Installer
4. ไม่ใช้ Developer Hash Whitelist กับ Plugin v4 อีกต่อไป เพราะการกดติดตั้งถือเป็นการอนุญาตจากผู้ใช้ ต่างจาก v3 ที่มีเฉพาะ Adapter ฝัง Core
5. มีเฉพาะการติดตั้งและถอนติดตั้ง ไม่ซ่อม Runtime ถ้าไฟล์มีการเปลี่ยนแปลงเองจะไม่ลบโดยพลการ
6. ผู้สร้างแพ็กเกจยังต้องมีสิทธิ์แจกโมเดล, Native Libraries และ Wheel เอง การยอมรับของผู้ใช้ไม่เปลี่ยน License เช่น NC หรือ GPL

## สถานะ

- Core รองรับ TTS Worker แบบ Python 3.11 + Offline Wheels หรือ Native EXE จากแพ็กเกจ v4
- v3 ที่ติดตั้งอยู่แล้วสามารถทำงานต่อได้ ไม่แปลงไฟล์ v3 เป็น v4 อัตโนมัติ
- Translation Worker Protocol v1 รองรับการเชื่อม M2M100 v4 แบบออฟไลน์; STT และ LLM Plugin Protocol ยังเป็นงานขยายในอนาคต
- การพัฒนา v4 ไม่เท่ากับการออก Public Release ใหม่ หรือเป็นการยืนยันสิทธิ์แจกจ่าย Kokoro, Vachana และ Wayu NC
