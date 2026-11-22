# VoxWeaveTTS — Server / Remote Client (LAN)

## ไฟล์ตัวอย่าง (มีคอมเมนต์อธิบาย)

- Server: `config/network.examples.jsonc` แสดงตัวอย่างเครื่องเดียว, LAN, รับทุก NIC และเปลี่ยน Port
- Client: `config/client-connection.examples.jsonc` แสดงตัวอย่างเชื่อมต่อเครื่องเดียว, เครื่องอื่น และ Custom Port

ไฟล์ `.jsonc` เป็นตัวอย่างสำหรับอ่าน **ไม่ใช่ไฟล์ตั้งค่าที่โปรแกรมอ่านจริง** เพราะ JSON มาตรฐานไม่รองรับคอมเมนต์ ให้กรอกในหน้า **ตั้งค่า** ตามตัวอย่าง แล้วโปรแกรมจะบันทึกค่าเป็น JSON ที่ถูกต้องให้อัตโนมัติ โดยไม่เก็บ Password ของ Client และไม่เก็บ Password แบบ plaintext บน Server

## วิธีใช้งานแบบง่าย

เครื่องที่มี VoxWeaveTTS Server เป็นเครื่องสร้างเสียงและจัดการคิวทั้งหมด ส่วน VoxWeaveTTS Client ที่นำไปเปิดเครื่องอื่นเป็นเพียงหน้าต่างส่งคำสั่งและดูสถานะผ่าน API **ไม่ต้องลง TTS Engine และไม่ต้องติดตั้งโมเดลบน Client**

1. เครื่อง **Server**: เปิด `VoxWeaveTTS.exe` แล้วเข้าแท็บ **ตั้งค่า** → **การเชื่อมต่อ Server / Client ผ่าน LAN**
2. ติ๊ก **เปิดรับคำสั่งจาก Client ผ่าน LAN** เลือก Server IP ที่เครื่องนี้ใช้งาน เช่น `192.168.1.165` หรือ `0.0.0.0` (ทุกการ์ดเครือข่าย) และ Control Port เช่น `8776`
3. Username เริ่มต้นคือ `voxweave` สามารถเปลี่ยนได้ ตั้ง Password ความยาว **4–128 ตัวอักษร** แล้วกด **บันทึกการเชื่อมต่อ**
4. **ปิดและเปิด Core ใหม่** เพื่อให้การเปลี่ยน IP, Port, Username หรือ Password มีผล
5. เครื่องอื่นใน LAN: แตกไฟล์ `VoxWeaveTTS-Client-*-portable.zip` แล้วเปิด `VoxWeaveTTS-Client.exe` หรือ `Start-Client.cmd`
6. กรอก Server IP, **Control Port**, Username และ Password แล้วกด **เชื่อมต่อ Server** ใช้ปุ่มส่งข้อความ, เปลี่ยนปลายทางเสียง, เล่นซ้ำ หรือหยุดเสียงได้โดยส่งคำสั่งไปยัง Core บน Server

### พอร์ต (เปลี่ยนได้ทุกช่องในแท็บตั้งค่า)

| พอร์ตเริ่มต้น | ใช้สำหรับ | เข้าถึง |
|---|---|---|
| 8765 | Main Core API / Web UI | เฉพาะเครื่อง Server (`127.0.0.1`) |
| 8766 | Live Audio Listener บน Browser/โทรศัพท์ | LAN/IP ที่กำหนด |
| 8776 | Remote Desktop Client API (username/password) | LAN/IP ที่กำหนดหลังเปิดใช้งาน |

**ห้ามใช้หมายเลขพอร์ตซ้ำ**; เปลี่ยนทุกพอร์ตได้ตั้งแต่ 1–65535. การเปลี่ยน Core API Port จะอัปเดตการเปิดโปรแกรมใน `VoxWeaveTTS.exe`, `Start-Console.cmd` และ `Start-Desktop.cmd` เมื่อเปิด Core รอบใหม่

### การตั้งค่าและข้อมูลส่วนตัว

- Server บันทึกการเชื่อมต่อที่ `data/settings/network.json` (พาธสัมพันธ์กับโฟลเดอร์ Server) ไม่อ้างอิงไดรฟ์เดิม
- Username เป็นชื่อผู้ควบคุม (ค่าเริ่มต้น `voxweave`) **ไม่ใช่ชื่อแอป**
- Password จะเก็บบน Server เป็น PBKDF2-SHA256 แบบสุ่ม salt (ไม่เก็บรหัสผ่านจริง ไม่คืนแฮชผ่าน API)
- Client เก็บเพียง IP, Port, Username ที่ `data/client-connection.json`, **ไม่เก็บ Password ลงไฟล์**
- Remote Control Gateway อนุญาตเฉพาะคำสั่งดูสถานะงาน/คิว, สร้างเสียง, เล่นซ้ำ, หยุดเสียง, เปลี่ยนโหมดและอุปกรณ์เสียงเท่านั้น ไม่เปิดหน้า Model Packages, ข้อมูลบัญชี, ตั้งค่าลับ หรือดาวน์โหลด WAV
- Live Audio Listener ที่พอร์ต 8766 ยังคงส่ง PCM16 เป็นชิ้นสด ไม่ใช่ไฟล์เสียงย้อนหลัง
- การปิด Remote Client ไม่หยุด Core ที่ Server

**ความปลอดภัย:** พอร์ต Remote Control ใช้ HTTP Basic Authentication บน LAN จึงไม่เข้ารหัส Username/Password ระหว่างส่งข้อมูล โปรดใช้เฉพาะ LAN ที่ไว้ใจได้หรือ VPN ที่ปลอดภัย **ห้ามเปิดพอร์ต 8776 ออกอินเทอร์เน็ตโดยตรง** การลดรหัสขั้นต่ำเหลือ 4 ตัวอักษรเพิ่มความเสี่ยงจากการเดารหัส จึงควรใช้รหัสยาวขึ้นเมื่อใช้งานจริง

### การบรรจุแพ็กเกจ

- Server ZIP: `VoxWeaveTTS-v<version>-portable.zip` (Core/Web/Desktop/Engine package management)
- Client ZIP: `VoxWeaveTTS-Client-v<version>-portable.zip` (Python/Tk UI + API Client เท่านั้น)
- ทั้งสอง ZIP รองรับ Relocatable: ย้ายโฟลเดอร์ได้โดยไม่มีพาธไดรฟ์ตายตัว; Client ไม่มี TTS Engine/Model/PortAudio
- สร้าง Client ZIP ด้วย `powershell -ExecutionPolicy Bypass -File scripts/Build-Client-Portable.ps1`
