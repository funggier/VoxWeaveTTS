# VoxWeaveTTS — Remote Desktop Client API (ตัวเลือกขั้นสูง)

**ส่วนนี้สำหรับโปรแกรม `VoxWeaveTTS-Client.exe` เท่านั้น** ไม่ใช่สำหรับการเปิดเว็บควบคุมจากโทรศัพท์หรือคอมพิวเตอร์เครื่องอื่น

หากต้องการใช้ **Browser ควบคุม Server ผ่าน LAN** ให้เปิด IP/Port ของ **Web Control** จาก Launcher (`VoxWeaveTTS.exe`) เช่น `http://192.168.1.165:8775/` **ไม่จำเป็นต้องเปิด Remote Desktop Client API** ดู [คู่มือ LAN ทั้ง 3 ช่องทาง](LAN_CONNECTIONS_TH.md)

การพัฒนา Remote Desktop Client แยกพักไว้ก่อน เพื่อเน้นการทำงานของ Core และ Browser Control แต่ยังเก็บการตั้งค่าที่มีอยู่ไว้สำหรับอนาคต

## การตั้งค่าที่เกี่ยวข้อง (อย่าสับสนระหว่างสองชุด)

| ส่วน | ตั้งค่า | เก็บที่ | ตัวอย่าง |
|---|---|---|---|
| **Web Control (Browser)** | ใน Launcher บนเครื่อง Server | `data/network.json` | `192.168.1.165:8775` |
| **Live Audio Listener** | แท็บ **ตั้งค่า → Browser รับฟังเสียงสด** | `data/settings/network.json` | `192.168.1.165:8766` |
| **Remote Desktop Client API** | แท็บ **ตั้งค่า → Remote Desktop Client API (ขั้นสูง)** | `data/settings/network.json` | `192.168.1.165:8776` |

Username/Password สำหรับ **Web Control** ตั้งใน Launcher ส่วน Username/Password สำหรับ **Remote Desktop Client API** ตั้งแยกในหัวข้อขั้นสูง แม้ตั้งชื่อผู้ใช้เหมือนกัน ก็เป็นบัญชีคนละชุด

พอร์ตทั้งสามช่องทางเปลี่ยนได้ แต่ต้องไม่ใช้หมายเลขซ้ำกัน ค่าตัวอย่างในคู่มือไม่ใช่พอร์ตบังคับ

## การเปิดใช้ Remote Desktop Client API เฉพาะเมื่อจำเป็น

1. เปิด Web Control **บนเครื่อง Server** → **ตั้งค่า** → ขยาย **Remote Desktop Client API — ตัวเลือกขั้นสูง**
2. เปิด **Remote Desktop Client API** แล้วกำหนด IP ที่เปิดรับ (เช่น `192.168.1.165` หรือ `0.0.0.0`) และพอร์ตสำหรับ Client (เช่น `8776`)
3. ตั้ง Username และ Password อย่างน้อย 4 ตัวอักษร แล้วกด **บันทึก Remote Client**
4. เริ่ม Core ใหม่ แล้วตรวจสถานะว่าพอร์ต Remote Client เปิดรับอยู่จริง
5. บนเครื่อง Client แยก เปิด `VoxWeaveTTS-Client.exe` แล้วกรอก **Server IP + Remote Client Port + Username + Password** ของส่วน Remote API นี้ ไม่ใช่พอร์ต Web Control

การปิดหน้าต่าง Client ไม่ทำให้ Core บน Server หยุด และเครื่อง Client ไม่จำเป็นต้องติดตั้งโมเดลหรือ TTS Engine

## การเก็บข้อมูลและตัวอย่าง

- `config/network.examples.jsonc` แสดงตัวอย่าง Live Audio Listener และ Remote Desktop Client API พร้อมคอมเมนต์ **ไม่ใช่ไฟล์ตั้งค่าจริง**
- `config/client-connection.examples.jsonc` แสดงตัวอย่างโปรแกรม Client เฉพาะทาง
- Password ของ Remote Desktop Client API เก็บบน Server เป็นแฮช PBKDF2-SHA256; Client ไม่บันทึก Password ไว้ในไฟล์
- การตั้งค่าทั้งหมดเป็นไฟล์สัมพัทธ์ภายในโฟลเดอร์ Portable รองรับการย้ายไดรฟ์หรือย้ายโฟลเดอร์

**ความปลอดภัย:** Remote API ส่ง Username/Password ผ่าน HTTP Basic ใน LAN จึงควรใช้เฉพาะ LAN/VPN ที่เชื่อถือได้ อย่าเปิดพอร์ต Remote Client ออกอินเทอร์เน็ตโดยตรง และควรใช้รหัสที่แข็งแรงกว่าขั้นต่ำ 4 ตัวอักษร
