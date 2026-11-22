# VoxWeaveTTS v0.12.14 — VoxWeaveSTT (API)

## ดาวน์โหลด

- **VoxWeaveTTS-v0.12.14-portable.zip** — โปรแกรม Server/Core Portable บน Windows พร้อมหน้า Web Control และโหมด VoxWeaveSTT (API)
- **VoxWeaveTTS-Client-v0.12.14-portable.zip** — โปรแกรม Remote Desktop Client Portable สำหรับควบคุม Server
- **SHA256SUMS-v0.12.14.txt** — ค่า SHA-256 สำหรับ ZIP ทั้งสองไฟล์

แพ็กเกจ Server/Core ไม่รวมโมเดลเสียง ติดตั้งโมเดลที่ต้องการผ่าน .vwmodel v4 ตามสิทธิ์ของโมเดลนั้น

## ความสามารถใหม่

1. โหมด **VoxWeaveSTT (API)** ใหม่ พร้อมช่อง IP / Port (เริ่มต้น 127.0.0.1:8766) และปุ่มเชื่อมต่อ/หยุดรับข้อความ
2. อ่านเฉพาะ Final Transcript (`transcript.final`) จาก STT API เดิม รับเป็นลำดับตาม cursor ไม่เล่นข้อความเก่า และป้องกันการรับซ้ำ
3. ใช้ Core แหล่งข้อความเดิม: กฎคำอ่าน การแปล/AI Processing โมเดลเสียงตามภาษา คิวและ Subtitle
4. รักษา Computer Core-first จาก v0.12.13: ไม่ต้องเปิดหน้าเว็บค้างไว้เมื่อ Core เป็นผู้เล่นเสียง; Browser ใช้แสดงข้อมูลและควบคุม
5. เชื่อม STT ใน LAN ผ่าน HTTPS พร้อม PIN และ SHA-256 Certificate Fingerprint ตามระบบจับคู่ STT (ไม่รองรับ HTTP ข้ามเครื่อง)
6. ตัวเลือกขั้นสูงยุบเก็บได้ ปรับ mapping JavaScript ให้ใช้ร่วมกันมากขึ้น ลดการทำซ้ำ

## วิธีใช้งาน

1. เปิด VoxWeaveSTT และเริ่มถอดเสียง
2. เปิด VoxWeaveTTS → **VoxWeaveSTT (API)**
3. ระบุ IP `127.0.0.1` และ Port `8766` → กด **เชื่อมต่อ STT**
4. Final Transcript ใหม่จะเข้าคิวเสียง; ถ้า STT ยังไม่เริ่ม Session โปรแกรมจะรอจนกว่าจะเริ่ม
5. กด **หยุดรับข้อความ** เพื่อหยุดเฉพาะการรับ โดยไม่ปิด STT

สำหรับ LAN ให้เปิด HTTPS LAN Gateway ฝั่ง STT ก่อน แล้วใส่ IP/Port Gateway (โดยทั่วไป 8768), PIN และ SHA-256 Fingerprint

## ข้อควรทราบ

- หาก STT รับ Desktop Loopback ของอุปกรณ์ที่ TTS เล่น อาจเกิดวงจรเสียงสะท้อนและอ่านตัวเองซ้ำ ต้องแยกแหล่งเสียงก่อนเปิดอัตโนมัติ
- เป็นการรับข้อความ Final เท่านั้น ไม่ใช่ระบบพากย์ทับตำแหน่งเวลาของเสียงต้นฉบับ
- Browser playback ยังขึ้นกับสิทธิ์ Autoplay; Computer mode ให้ Core จัดการ playback
- ไม่ต้องออก STT รุ่นใหม่เพื่อใช้งานในเครื่องเดียวกัน เพราะใช้ API ที่ STT มีอยู่แล้ว

ดู [คู่มือ STT API](STT_API_MODE_TH.md), [Core Control](RUNTIME_API_LIVE_TH.md) และ [คู่มือ LAN](LAN_CONNECTIONS_TH.md)
