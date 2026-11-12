# VoxWeaveTTS v0.4.2 — Windows Portable

## ดาวน์โหลด / Download

**VoxWeaveTTS-v0.4.2-portable.zip** — แอป Windows 10/11 x64 แบบ Portable พร้อม Python Runtime, Web UI, OBS Overlay และ **MakHam Paradee Thai INT8 (CPU ONNX)**

แตก ZIP ทั้งชุดไปยังโฟลเดอร์ที่เขียนได้ เช่น `T:\Apps\VoxWeaveTTS` แล้วเปิด `VoxWeaveTTS.exe` ไม่ต้องติดตั้ง Python, Node หรือ GitHub CLI

หาก Windows ป้องกัน EXE ที่ไม่ได้ลงลายเซ็น ใช้ `Start-Console.cmd` แทน แล้วเปิด http://127.0.0.1:8765/ ด้วย Firefox หรือ Chrome

โปรแกรมผูก API กับ `127.0.0.1` เท่านั้น ไม่ควรเปิดพอร์ตให้เข้าถึงจากอินเทอร์เน็ตโดยตรง

## มีอะไรใหม่ / Highlights

- **หลายช่องทางพร้อมกัน:** YouTube LIVE, TikTok LIVE (TikFinity), Discord Bot, Discord Desktop Client และ Studio/Document Reader ทำงานพร้อมกันได้ การสลับแท็บไม่หยุดช่องทางอื่นที่เชื่อมต่ออยู่
- **จัดคิวเสียง:** เลือก **เล่นทีละเสียง (ไม่ซ้อน)** หรือ **เล่นพร้อมกัน (เสียงซ้อนได้)** ค่าเริ่มต้นเป็นเล่นทีละเสียง
- **เสียงแยกตามช่องทาง:** ตั้ง Engine/Model, Voice, Speed, Gain, Pitch, Bass, Treble, Formant Preserve และ Seed ของแต่ละโหมดได้อิสระ ความเร็ว `×0.60–×5.00` และช่องตัวเลขสำหรับค่าปรับเสียงละเอียด `0.01` การเปลี่ยนจะมีผลกับงานสร้างเสียงถัดไป
- **อ่านชื่อผู้ส่งหรือไม่:** ช่อง YouTube LIVE, TikTok LIVE, Discord Bot และ Discord Client มีตัวเลือกของตนเอง ปิดเป็นค่าเริ่มต้น เมื่อเปิดจะอ่าน `ชื่อผู้ส่ง พิมพ์ว่า ข้อความ` โดยยังแสดงชื่อผู้ส่งในรายการข้อความตามปกติ
- **คงค่าอ่านข้อความใหม่อัตโนมัติ:** ข้อผิดพลาดของ Browser/เสียงจะพักคิวชั่วคราว ไม่เปลี่ยนตัวเลือกเป็น False เอง มีปุ่มลองอ่านต่อ
- **Voice Preset แบบพกพา:** Preset แต่ละรายการเป็นไฟล์ JSON ใน `presets/` สามารถคัดลอกมาจากอีกเครื่องแล้วกดรีเฟรช Dropdown แม้โมเดลของ Preset นั้นยังไม่ได้ติดตั้ง
- **Model Packages (`.vwmodel`):** ติดตั้งโมเดลเสริมหลายแพ็กเกจและหลายเสียงผ่านแท็บ **ตั้งค่า** รองรับข้อมูล License, Source, Dependencies, SHA-256 และการถอนการติดตั้ง
- **Export/Import รายช่องทาง:** บันทึก/โหลดการตั้งค่าการเชื่อมต่อได้ รวมถึงตัวเลือกอ่านชื่อผู้ส่ง รองรับ Firefox และ Chrome ไฟล์รุ่นก่อนหน้ายังนำเข้าได้

## โมเดลใน ZIP และ Model Packages

**บันเดิล MakHam Paradee เท่านั้น** พร้อมแหล่งที่มาและลิขสิทธิ์ใน `THIRD_PARTY_NOTICES.txt` และ `docs/COMMERCIAL_LICENSE_POLICY_TH.md`

**ไม่มีโมเดล Vachana 4 Voices หรือ FastThaiG2P Kokoro Thai Som แนบใน GitHub Release นี้** แม้ระบบรับไฟล์ `.vwmodel` และได้ทดลองสร้างเสียงจากแพ็กเกจเหล่านั้นในเครื่องแล้ว แต่สิทธิ์/ที่มาของน้ำหนักโมเดลยังต้องตรวจให้ครบ และ Runtime Dependencies ของ Vachana อาจไม่ครบใน Portable นี้ จึงไม่ควรถือว่าติดตั้งแพ็กเกจแล้วใช้งานได้แน่นอนโดยไม่ตรวจ Dependencies

**อย่าส่งไฟล์ Export โปรไฟล์การเชื่อมต่อสาธารณะ** หากมี API Key, Bot Token หรือ Application Client Secret เพราะระบบบันทึกตามที่กรอกเป็นข้อความธรรมดาใน JSON เพื่อให้ผู้ใช้ย้ายการตั้งค่าข้ามเครื่องได้

## การตั้งค่าครั้งแรก

1. แตก ZIP ไปยังโฟลเดอร์ที่สามารถเขียนไฟล์ได้ แล้วเปิด `VoxWeaveTTS.exe`
2. เปิด http://127.0.0.1:8765/ แล้วลองสร้างเสียงด้วย MakHam Paradee
3. หากต้องการอ่านคอมเมนต์สด ให้เข้าแท็บของช่องทางนั้น กรอกข้อมูลบัญชี/ห้องตามสิทธิ์ที่ได้รับ แล้ว **กดเชื่อมต่อ** เอง
4. เลือกอ่านชื่อผู้ส่งและเสียงของแต่ละช่องทาง ตั้งค่าเล่นทีละเสียงหรืออนุญาตเสียงซ้อนบนแถบบน
5. ดู/บันทึก Voice Preset ได้จาก `presets/` และติดตั้ง Model Packages เพิ่มผ่านแท็บ **ตั้งค่า**
6. ใช้ `Stop & Exit` เพื่อปิด Backend เมื่อเลิกใช้งาน

## ผลทดสอบ / Verification

- Python unit tests: **185 passed**
- JavaScript UI/queue smoke tests: **17 suites passed**
- Windows x64 standalone ZIP: extraction, runtime import, Thai WAV generation and HTTP speech synthesis verified
- GitHub Actions CI on Python 3.11 and 3.13: verified before release
- Discord Desktop RPC message retrieval: previously confirmed by the user; running **all** Live providers simultaneously with real accounts has not been verified
- TikTok LIVE via TikFinity is a third-party local WebSocket integration, not an official public TikTok LIVE API

## ข้อจำกัดสำคัญ

ยังไม่มี Voice Cloning หรือโมเดลฝึกเอง, Native Emotion/Formant synthesis, automatic word-level alignment หรือ Hardware Playback Clock. เมื่ออนุญาตให้เล่นเสียงซ้อน OBS Overlay เดิมแสดง Subtitle หลักเพียงชุดเดียว (Backend มี API รายช่องทาง). บาง Engine/เสียงปรับ DSP ต้องใช้ FFmpeg/Rubber Band เพิ่มเติม และความเร็วจริงที่ได้อาจไม่เท่ากับค่าทวีคูณทุก Engine

อ่านรายละเอียด: [คู่มือ Portable](PORTABLE.md), [การทำงานพร้อมกัน](WORKSPACE_MODES_TH.md), [Model Packages](MODEL_PACKAGES_TH.md), [นโยบายสิทธิ์](COMMERCIAL_LICENSE_POLICY_TH.md)

Source: https://github.com/funggier/VoxWeaveTTS
