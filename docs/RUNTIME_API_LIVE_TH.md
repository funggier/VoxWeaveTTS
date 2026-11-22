# VoxWeaveTTS — Local API, Desktop UI และ Live Audio (Portable)

**ตัวอย่าง IP/Port/Username พร้อมคอมเมนต์:** อ่าน `config/network.examples.jsonc` (Server) และ `config/client-connection.examples.jsonc` (Client). แก้ค่าจริงในแท็บ **ตั้งค่า** ไม่ต้องแก้ JSON เอง; ดู [คู่มือ Remote Client](REMOTE_CONTROL_CLIENT_TH.md)

## สถาปัตยกรรม

- **Core:** โปรแกรม Python ในเครื่องเป็นเจ้าของการรับข้อความ, คิวสร้าง TTS, การเล่นเสียงและสถานะ ไม่ขึ้นกับการเปิด Browser หรือหน้าต่าง Desktop UI
- **Web UI:** `http://127.0.0.1:8765/` ใช้เรียก API เดียวกับ Desktop UI และยังรองรับการทำงานผ่านเบราว์เซอร์แบบเดิม
- **Desktop UI:** เปิดด้วย `Start-Desktop.cmd` หรือปุ่ม **Open Desktop UI** ใน `VoxWeaveTTS.exe` โดยเป็นเพียง API client; ปิดหน้าต่างได้โดยไม่สั่ง Core หยุด
- **Live Listener:** `http://<LAN-IP>:8766/listen#token=...` (ลิงก์จริงแสดงใน **ตั้งค่า**) รับ PCM16 mono ผ่านสตรีม HTTP/SSE ต่อเนื่อง; **ไม่มี endpoint สำหรับดาวน์โหลด WAV หรือเล่นคิวย้อนหลังในตัวรับฟัง** และเปิดฟังระหว่างเพลง/เสียงพูดได้ทันที

## ตั้งค่า

เปิดแท็บ **ตั้งค่า** (Web UI) หรือแท็บ **ตั้งค่า** (Desktop UI) แล้วเลือก:

1. **รูปแบบการทำงาน**
   - `browser`: โหมดเดิม ผู้ใช้เปิด Web UI ที่ควบคุมการเล่นเสียง ผ่าน HTMLMediaElement
   - `computer`: Core รับและสร้างเสียง/เล่นบนเครื่องเอง แม้ไม่มี Web UI เปิดอยู่
2. **ส่งเสียงออกทาง**
   - `default`: Windows default output
   - `wasapi:<ชื่ออุปกรณ์>`: Windows speaker / USB DAC / headphone endpoint ที่มีอยู่จริง; ตรวจพบชื่อใหม่จากเครื่องทุกครั้ง ไม่บันทึก index อุปกรณ์
   - `live`: ส่ง PCM16 สดให้ผู้ฟังผ่านเบราว์เซอร์ทาง LAN และ **ไม่เล่นเสียงซ้ำ** ออกจากลำโพงคอม

ในโหมด `computer`, คลิก **เล่นซ้ำเสียงล่าสุดผ่าน API** เพื่อเริ่มเล่นเสียงที่ Core เก็บไว้ในหน่วยความจำอีกครั้งที่ปลายทางที่เลือก ปุ่ม **หยุดเสียง** ก็สั่ง Core ผ่าน API เดียวกัน

### API หลัก

| Method | Endpoint | ความหมาย |
| --- | --- | --- |
| GET | `/v1/runtime/state` | สถานะ Core, คิว, อุปกรณ์, ลิงก์ผู้ฟังสด |
| POST | `/v1/runtime/mode` | `{"mode":"browser"|"computer"}` / intent `set-runtime-mode` |
| POST | `/v1/runtime/output` | `{"output":"default"|"live"|"wasapi:..."}` / intent `set-runtime-output` |
| POST | `/v1/runtime/replay` | `{}` / intent `replay-computer-audio` |
| POST | `/v1/runtime/playback` | `{"action":"stop"}` / intent `control-computer-playback` |
| POST | `/v1/jobs` | สั่งสร้างเสียงด้วย API คิวงานเดิม / intent `queue-speech` |
| GET | `/v1/playback/state` | สถานะ subtitle/playback จาก Core |

บนช่องทาง LAN (`8766`) อนุญาตเฉพาะ `GET /listen`, `GET /v1/live/stream`, `GET /v1/live/status`, `POST /v1/live/replay` และ `POST /v1/live/stop`. ยกเว้นหน้า `/listen` ทุก endpoint ต้องส่ง `Authorization: Bearer <token>`. หน้าเว็บอ่าน token จาก URL fragment และส่งเป็น header; ไม่ใส่ใน URL query เพื่อไม่ติด access log. ส่วน API หลักยัง bind เฉพาะ `127.0.0.1` (loopback) เหมือนเดิม

### ความหมายของคำว่า Live

Live ในระบบนี้หมายถึงส่งกรอบ PCM16 ระยะประมาณ 100 มิลลิวินาทีจากโปรเซส Core ต่อเนื่องบนเครือข่ายเดียวกัน ไม่ใช่การดาวน์โหลดไฟล์ WAV ทีละข้อความ คิวผู้ฟังมีเพดานต่ำ: เมื่อรับข้อมูลช้าจะข้ามเสียงค้างเพื่อกลับสู่เวลาสด เบราว์เซอร์ใช้ AudioContext เล่น PCM ที่รับมา หลังผู้ใช้กด **เปิดรับฟังเสียงสด** ด้วยตนเองหนึ่งครั้ง

เสียงที่ปล่อยจากตัวส่งสดอาจมีดีเลย์ประมาณระดับหลายร้อยมิลลิวินาทีตามเครือข่ายและ Web Audio buffer ไม่รับประกัน hard real-time; สำหรับ subtitle ที่รายงานจาก Core เป็นเวลาโดยประมาณ (monotonic) ไม่ใช่เวลาอุปกรณ์จริง

### Portable / Relocatable

- ตำแหน่ง settings: `data/settings/runtime-control.json` (ภายในโฟลเดอร์โปรแกรม)
- ตำแหน่งแคช: `cache/`, `cache/temp/`, `runtime/`, `models/` ภายในโฟลเดอร์เดียวกัน
- พาธจริงมาจาก `Path(__file__).resolve().parents[2]` และ `%~dp0`, ไม่ผูกกับ `T:\\`, `C:\\` หรือเครื่องใดเครื่องหนึ่ง
- Portable ZIP ต้องแนบ `runtime/python`, `sounddevice`, `_sounddevice`, `_sounddevice_data`, `cffi` และ `pycparser` รวมถึงไฟล์ license; ไม่ต้องเรียก pip ระหว่างเปิดใช้งาน
- ย้ายทั้งโฟลเดอร์โปรแกรมขณะ Core หยุดทำงาน แล้วเปิดใหม่ที่ตำแหน่งใหม่ได้ทันที ถ้าย้ายคอมและอุปกรณ์เดิมไม่มี ให้เลือกอุปกรณ์เสียงใหม่ในหน้า ตั้งค่า

### ข้อจำกัดด้านการเชื่อมต่อและความปลอดภัย

- โทรศัพท์ต้องอยู่ LAN เดียวกันกับคอม (หรือ VPN ที่ผู้ใช้ตั้งค่าเอง), เปิดพอร์ต 8766 ให้ถึงคอมบนเครือข่ายที่ไว้ใจได้; ไม่แนะนำเปิดพอร์ตนี้ออกอินเทอร์เน็ต เนื่องจากเป็น HTTP ไม่เข้ารหัส
- ลิงก์ผู้ฟังมี Bearer token ของการรัน Core ครั้งนั้น ผู้ได้ลิงก์สามารถรับเสียงสดและสั่งเล่นซ้ำ/หยุดเสียงได้ จึงควรเก็บเป็นส่วนตัว
- โทรศัพท์ต้องเปิดหน้า `listen` ไว้; มือถือบางเครื่องจะพักการทำงานเมื่อล็อกจอ/สลับแอปตามนโยบายพลังงานของเบราว์เซอร์
- แหล่งที่ต้องใช้ Chrome extension หรือ browser DOM ขึ้นกับหน้าต่างรับแชทที่เกี่ยวข้องต่อไป; การปิด Web UI ควบคุมไม่ได้ปิด source worker ที่รันบน Python
- ขณะนี้ live output ส่ง TTS ใหม่เป็นกรอบ PCM16 mono จาก Core โดยเลือกปลายทางหลักได้ครั้งละหนึ่งแบบ; นี่ไม่ใช่ระบบ broadcast เสียงทุกอย่างจากระบบปฏิบัติการ
