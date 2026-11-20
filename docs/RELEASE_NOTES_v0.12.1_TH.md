# VoxWeaveTTS v0.12.1 — Universal v4 Core-only + Windows Desktop Speech

**Release date:** 20 พฤศจิกายน 2026

**รุ่น:** Windows 10/11 x64 Portable, รองรับเฉพาะ Universal `.vwmodel v4`. โปรแกรม Core ไม่แนบน้ำหนักโมเดล TTS/Translation หรือ Runtime ของโมเดล ML ใน ZIP

## สิ่งใหม่

- เพิ่มแพ็กเกจ `VoxWeaveTTS-Windows-SAPI-Desktop-v1.0.0-format-v4.vwmodel` เป็น **TTS ที่พูดได้จริง** โดยใช้ **Windows System.Speech / SAPI Desktop Voices ที่ติดตั้งในเครื่องผู้ใช้เอง** ไม่บรรจุไฟล์ Voice, Weights หรือ DLL ของ Microsoft ไว้ในแพ็กเกจ
- Worker v4 สร้างเสียง **PCM16 mono 16,000 Hz** ใช้เสียง Default / Female / Male (สองตัวหลังเลือกเสียงที่มีในเครื่องและกลับไป Default หากไม่มี) ออกผ่าน Queue, API และระบบเสียงของ Core ตาม Worker Protocol v1
- ปรับความเร็วด้วย SAPI Rate (-10 ถึง 10): **ไม่ใช่ตัวคูณความเร็วที่แม่นยำ** แม้ UI มีค่าความเร็วเป็นตัวคูณ
- โปรแกรมเรียก Windows PowerShell 5.1 ด้วยโค้ดที่กำหนดตายตัว ข้อความผู้ใช้ส่งเป็น JSON ผ่าน STDIN ไม่ฝังลงในคำสั่ง/สคริปต์ที่รัน
- ซอร์สแพ็กเกจและตัวอย่าง v4 เพิ่มที่ `examples/v4-windows-sapi/` พร้อมชุดทดสอบการแพ็ก การป้องกัน Command Injection และการสร้างเสียงจริง
- รวมงานตรวจ **ความเหมือนของน้ำหนักโมเดล v2/v3/v4** (SHA-256) และการจัดเก็บหลักฐาน LICENSE/NOTICE ต้นฉบับของ Wheel ลงในแนวทาง QA ใน Git; ไม่แก้ License เดิมของโมเดล

## วิธีเริ่มใช้

1. ดาวน์โหลด `VoxWeaveTTS-v0.12.1-portable.zip` และแตกไปยังไดเรกทอรีใดก็ได้บน Windows x64
2. เปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd`; เข้า `http://127.0.0.1:8765/` (ถ้าพอร์ตนี้ไม่มีโปรแกรมอื่นใช้อยู่)
3. ดาวน์โหลดแพ็กเกจ Windows SAPI v4 แยกจากหน้า Release นี้ แล้วไปที่ **ตั้งค่า → จัดการโมเดล** เลือกไฟล์ `.vwmodel` ติดตั้งแบบออฟไลน์
4. เลือก Engine `Windows SAPI Desktop` และเสียงที่ต้องการเพื่ออ่านข้อความภาษาอังกฤษ
5. หากต้องการทดลองเฉพาะ Protocol ให้ใช้แพ็กเกจ `VoxWeaveTTS-v0.12.1-v4-demo-tone.vwmodel` ซึ่ง **เป็นเสียงโทน ไม่ใช่เสียงพูด**

**ข้อจำกัด SAPI:** ต้องมี Windows PowerShell 5.1, `.NET Framework System.Speech` และเสียง Desktop SAPI ที่เปิดใช้งานอยู่ใน Windows เครื่องปลายทาง (เสียง OneCore บางชนิดไม่ปรากฏใน SAPI Desktop) ปัจจุบันประกาศรองรับ **ภาษาอังกฤษ** เท่านั้น การอ่านไทยด้วยเสียงไทยยังต้องติดตั้งโมเดล/เสียงที่รองรับแยกเอง ตัวแพ็กเกจนี้เป็น Bridge ของ Windows ที่ผู้ใช้มีสิทธิ์ใช้ตาม License Windows/Voice ของตน ไม่ใช่โมเดล ML หรือ Voice Cloning และไม่รับรองว่าเสียงทุกเครื่องเหมือนกัน

## สิทธิ์โมเดลอื่นและการแจกจ่าย

- โมเดลจริง 8 ชุด (TTS 7 + Translation M2M100 1) เคยผ่านการติดตั้ง/Inference ออฟไลน์ใน QA และน้ำหนักเหมือน V2 ที่เคยเผยแพร่ตาม SHA-256; อย่างไรก็ดี **แพ็กเกจ V4 ของทั้ง 8 ยังไม่ได้รับอนุมัติ Public Redistribution** เพราะ Worker, Wheel, Native Binary หรือ Notices/Source Obligations บางรายการยังไม่พร้อม
- ไม่แนบ QA Packs ใดไว้ใน Release นี้ และไม่ปิด Release Gate เพียงเพราะเคยเผยแพร่ไฟล์น้ำหนักในรุ่นก่อน
- Wayu Paxa Edge NC ต้องคง **CC BY-NC 4.0** และ Acceptable Use; Supertonic 3 ต้องคง **OpenRAIL-M**. GPL/LGPL ไม่ได้แปลว่าแจกไม่ได้เสมอ แต่ต้องทำตามภาระ License, Notices และ Source ที่เกี่ยวข้อง
- โค้ด Bridge Windows SAPI เขียนภายใน VoxWeaveTTS และแจกภายใต้ MIT; ไม่แจกเสียงหรือ Library ที่เป็นทรัพย์สินของ Microsoft หรือเจ้าของเสียง
- การกดติดตั้งเป็นการเลือกเชื่อถือ Plugin ที่มีสิทธิ์ทำงานเป็นผู้ใช้ Windows ไม่ใช่ Sandbox หรือการอนุญาตให้ผู้เผยแพร่แจกไฟล์ของบุคคลที่สาม

ดู [หลักฐานสิทธิ์ต้นทาง](V4_UPSTREAM_LICENSE_EVIDENCE_TH.md), [ผลตรวจ V2/V3/V4](V4_MODEL_LICENSE_CONTINUITY_TH.md), [สิทธิ์แพ็กเกจ V4](V4_MODEL_PACK_RIGHTS_QA_2026-11-20_TH.md) และ [คู่มือ v4](UNIVERSAL_VWMODEL_V4_TH.md)

## การตรวจสอบคุณภาพก่อนออก Release

- Python unit regression และ JS browser smoke tests ผ่านบนเครื่องพัฒนา และ GitHub Actions Windows Python 3.11 / 3.13
- Python/Windows SAPI เรียกเสียงพูดอังกฤษจริง; ทดสอบติดตั้ง/ถอนแพ็กเกจผ่าน Core v4 และ WAV จาก Queue จริง (16 kHz mono PCM16)
- แตกไฟล์ Portable ZIP ไปโฟลเดอร์ชั่วคราว ทดสอบ API Loopback, YouTube gRPC, Demo Tone, SAPI และการถอนแพ็กเกจ; ตรวจ ZIP CRC, Hash, ไม่แอบรวมข้อมูลผู้ใช้หรือโมเดล QA
- เช็ค SHA-256 ของทุก Asset ใน `SHA256SUMS-v0.12.1.txt`

**ความสำเร็จบนเครื่องพัฒนาไม่รับประกันว่า Windows ทุกเครื่องมี SAPI desktop voice หรือคุณภาพเสียงเท่ากัน**; ยังไม่ได้ทดสอบกับเครื่อง Windows อีกเครื่องจริง
