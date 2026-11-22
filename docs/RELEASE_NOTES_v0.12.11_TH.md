# VoxWeaveTTS v0.12.11 — Local Core, Live Audio & Remote Client

**วันที่เผยแพร่:** 22 พฤศจิกายน 2026
**แพลตฟอร์ม:** Windows x64 Portable / Relocatable · Universal `.vwmodel` V4 เท่านั้น

## ดาวน์โหลดโปรแกรม

1. **VoxWeaveTTS-v0.12.11-portable.zip** — Server/Core, Web UI, หน้าต่าง Desktop UI, ระบบ TTS/แปล/ติดตั้งโมเดล, Live/Discord/YouTube/TikTok
2. **VoxWeaveTTS-Client-v0.12.11-portable.zip** — Remote Desktop Client ล้วน ๆ สำหรับเครื่องอื่น ไม่มีโมเดลหรือ TTS Engine
3. **SHA256SUMS-v0.12.11.txt** — ไฟล์ SHA-256 ตรวจความถูกต้องของ ZIP ทั้งสอง

ดาวน์โหลด ZIP ที่ต้องการจากแท็บ **Assets** ของ Release นี้ แยกติดตั้งได้โดยแตกไฟล์ ไม่ต้องติดตั้งโปรแกรมผ่าน Windows Installer

## ฟีเจอร์หลักของรุ่นนี้

- **Core บนคอมทำงานต่อแม้ปิดหน้า Web UI หรือ Desktop UI**: รับแชทที่เชื่อมต่อกับตัวรับบน Server, จัดคิว TTS และเล่นเสียงตามปลายทางที่กำหนด ไม่ใช้ Browser Timer เป็นตัวถือคิวหลัก
- **API ศูนย์กลาง**: Desktop UI และ Web UI สั่งงานผ่าน HTTP API เดียวกัน; เลือกโหมด `computer` หรือ `browser` ในแท็บ **ตั้งค่า** โดยยังรองรับพฤติกรรมเดิม
- **Audio output แบบเลือกได้**: Windows default, อุปกรณ์ Windows WASAPI เช่น USB DAC / ลำโพง, หรือ **Live Browser** ทาง LAN ซึ่งส่ง PCM16 เป็นชิ้นต่อเนื่อง ไม่มีระบบดาวน์โหลด WAV ในหน้า Listener
- **เล่นซ้ำเสียงล่าสุดและหยุดเสียงผ่าน API**: ส่งคำสั่งให้ Server เริ่มเล่นใหม่ ไม่ใช่ส่งไฟล์ WAV ไปยัง Client
- **Remote Client**: ตั้ง Server IP/Port, Username, Password บน Client; Server เปิด Remote API เฉพาะเมื่อเลือกไว้; แยก Client Portable ที่ไม่ต้องลงโมเดล
- **Network login เดิม**: ใน Launcher ของ Server เลือก Local/LAN/Tailnet/All IPv4 และแก้ Username ได้ (เริ่มต้น `voxweave`); รหัสสำหรับ LAN สั้นสุด 4 ตัวอักษร
- **ตัวอย่าง config แบบมีคอมเมนต์**: `config/network.examples.jsonc` และ `config/client-connection.examples.jsonc` แยกจากไฟล์ JSON ที่โปรแกรมใช้งานจริง
- **Portable / Relocatable**: พาธแคช/ตั้งค่า/โปรแกรมเป็นพาธสัมพัทธ์กับโฟลเดอร์; Server บันเดิล Python และไลบรารีเลือกอุปกรณ์เสียง; Client บันเดิลเฉพาะ Python/Tk และ Remote API Client

## วิธีเริ่มใช้งาน

**Server:** แตกไฟล์ Server ZIP → เปิด `VoxWeaveTTS.exe` → ตั้ง IP/Port และ Username/Password ตามต้องการ → เปิดหน้าต่าง Desktop หรือ Web UI → แท็บ **ตั้งค่า** เลือก `ทำงานในคอมพิวเตอร์` และปลายทางเสียง

**Client อีกเครื่อง:** แตกไฟล์ Client ZIP → เปิด `VoxWeaveTTS-Client.exe` → กรอก IP ของ Server, **Control Port (ค่าเริ่มต้น 8776)**, Username และ Password ที่ตั้งในแท็บตั้งค่า Server → เชื่อมต่อ หาก Server ใช้พอร์ตอื่น ให้กรอกตามค่าที่บันทึกไว้

**มือถือรับเสียงสด:** Server เลือกเอาต์พุต **Live Broadcast** → เปิดลิงก์ `Live Listener` ในแท็บตั้งค่าบนมือถือที่อยู่ LAN เดียวกัน → กด **เปิดรับฟังเสียงสด** หนึ่งครั้งเพื่ออนุญาตให้ Browser ส่งเสียง

อ่าน [คู่มือ Remote Control](docs/REMOTE_CONTROL_CLIENT_TH.md) และ [คู่มือ Runtime API/Live Audio](docs/RUNTIME_API_LIVE_TH.md) สำหรับตัวอย่างการตั้งค่า

## ดาวน์โหลดโมเดล V4 แยก

โมเดลทั้ง 7 แพ็กเกจอยู่ใน Release แพ็กเกจต้นทางที่เผยแพร่ก่อนหน้า (ไม่มีการแก้ไขหรือแจกไฟล์ซ้ำในรุ่นนี้):
**[ดาวน์โหลด Model Packs V4 ทั้ง 7 ตัว](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4)**

| โมเดล / หน้าที่ | ดาวน์โหลดแพ็กเกจ | สิทธิ์หลักตาม Release โมเดล |
|---|---|---|
| MakHam Paradee — TTS ภาษาไทย | [MakHam v4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-makham-paradee-1.0.0-format-v4.vwmodel) | Apache-2.0; แหล่งฝึกอ้างอิง CC BY 4.0 |
| FastThaiG2P Thai Som — TTS ภาษาไทย | [Thai Som v4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-fastthaig2p-thai-som-0.3.0-format-v4.vwmodel) | Apache-2.0 ตามแพ็กเกจ |
| Melo Chinese ONNX — TTS ภาษาจีน | [Melo Chinese v4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-melo-chinese-onnx-1.0.0-format-v4.vwmodel) | MIT ของโมเดล; Runtime แยกสิทธิ์ |
| Kokoro Multilingual INT8 — TTS หลายภาษา | [Kokoro v4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-kokoro-multilingual-int8-1.0.0-format-v4.vwmodel) | Apache-2.0 ของน้ำหนัก; GPLv3+ สำหรับบาง Dependency |
| Supertonic 3 Multilingual INT8 — TTS หลายภาษา | [Supertonic 3 v4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-supertonic3-multilingual-int8-1.0.0-format-v4.vwmodel) | OpenRAIL-M |
| Wayu Paxa Edge NC — TTS ไทย/อังกฤษ | [Wayu v4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-wayu-paxa-edge-nc-1.0.0-format-v4.vwmodel) | **CC BY-NC 4.0 — ไม่อนุญาตใช้เชิงพาณิชย์** |
| M2M100 418M — แปลภาษา Local (ไม่ใช่ TTS) | [M2M100 v4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/VoxWeaveTTS-m2m100-418m-1.0.0-format-v4.vwmodel) | MIT ตามโมเดล Repository; Runtime แยกสิทธิ์ |

ดาวน์โหลดเฉพาะโมเดลที่ต้องการ แล้วเปิดเมนูจัดการ Model Packages → เลือกไฟล์ `.vwmodel` → อ่านและยอมรับเงื่อนไขสิทธิ์ก่อนติดตั้ง โปรแกรมหลักไม่บันเดิลน้ำหนักโมเดล **Vachana ยังไม่รวม** เพราะยังไม่มีหลักฐานสิทธิ์แจกโค้ด `vachanatts` เพียงพอ

**ตรวจสอบไฟล์โมเดล:** [SHA256SUMS ของ Model Packs V4](https://github.com/funggier/VoxWeaveTTS/releases/download/v0.12.1-modelpacks-v4/SHA256SUMS-v0.12.1-modelpacks-v4.txt)

## ข้อจำกัดและความปลอดภัย

- **Live Audio** รับชมใน LAN/VPN ที่เชื่อถือได้เท่านั้น และไม่ใช่ HTTPS; โทรศัพท์บางเครื่องพักเสียงเมื่อสลับแอปหรือล็อกหน้าจอ ต้องกดอนุญาตเล่นเสียงก่อน
- **Remote Control API** ใช้ Username/Password ผ่าน HTTP Basic; ห้ามเปิดพอร์ตตรงออก Internet ควรใช้ VPN ที่ปกป้องทราฟฟิกและรหัสผ่านยาวพอในงานจริง
- Server มี **Web LAN login** ตามการตั้งค่าจาก Launcher (`data/network.json`) และ **Remote Client login** แยกในแท็บตั้งค่า (`data/settings/network.json`); ผู้ใช้สามารถกำหนด Username/Password เหมือนกันได้ แต่เป็นการตั้งค่าสองส่วน
- การปิดหน้าต่างควบคุมไม่หยุด Core แต่ **ตัวรับข้อความจาก Extension ที่อาศัย Browser ภายนอก** ยังคงต้องเปิด Browser/Extension นั้นตามข้อจำกัดของแหล่งข้อมูล
- ผู้ฟัง Live ไม่ดาวน์โหลด WAV ทั้งไฟล์; การบัฟเฟอร์เสียงเป็นช่วงสั้นอาจเกิดดีเลย์เล็กน้อย ไม่ใช่การสตรีมทั้งเสียงระบบปฏิบัติการ
- แพ็กเกจหลักไม่มีโมเดลและไม่มี License Server; ผู้ใช้ต้องนำเข้าแพ็กเกจ V4 เองและปฏิบัติตามสิทธิ์เดิมของโมเดลและ Dependencies
