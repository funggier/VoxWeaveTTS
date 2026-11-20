# ตัวอย่างสำหรับพัฒนา Model Package ของ VoxWeaveTTS v4

ตัวอย่างสำหรับสร้างส่วนเสริมใหม่ทั้งหมดในโฟลเดอร์นี้ใช้มาตรฐาน Universal .vwmodel v4 เท่านั้น

- v4-demo-tone: ตัวอย่าง Python Worker ขั้นพื้นฐานที่ไม่ต้องติดตั้ง Wheel
- v4-windows-sapi: **แพ็กเกจสร้างเสียงพูดอังกฤษจริงผ่าน Windows SAPI Desktop** ใช้เสียงของ Windows ที่ติดตั้งอยู่แล้ว ไม่แจกเสียง/ไลบรารีของ Microsoft และไม่ใช่โมเดล ML
- v4-demo-wheel: ตัวอย่างสร้าง Python Wheel ใหม่ในเครื่อง พร้อมบรรจุให้ติดตั้งออฟไลน์
- v4-native-worker: ตัวอย่าง Native Worker .exe เขียนด้วย C#
- v4-model-plugin: Worker สำหรับเชื่อมต่อ TTS หลายสถาปัตยกรรมจากแพ็กเกจอิสระ
- v4-translation-plugin: Worker แปลภาษาด้วย Protocol v1 และ Offline Model

ตัวอย่างเสียงโทนใช้พิสูจน์โครงสร้างเท่านั้น **ไม่ใช่โมเดล TTS ที่พูดจริง** ส่วน Windows SAPI เป็น Bridge ใช้เสียงของระบบปฏิบัติการที่ติดตั้งแยกอยู่ก่อนแล้ว (ขึ้นกับเสียง SAPI ที่เครื่องมี) และ Worker ของโมเดล ML จริงต้องใช้น้ำหนักโมเดลและ Wheel ที่มีสิทธิ์แจกจ่ายครบก่อนทำ Public Release

ดูคู่มือ docs/UNIVERSAL_VWMODEL_V4_TH.md และตัวสร้างแพ็กเกจ v4 แบบทั่วไป scripts/build_vwmodel_v4.py ซึ่งไม่ผูกกับสถาปัตยกรรมโมเดลใดโมเดลหนึ่ง

ตัวอย่างระบบ Provider รุ่นก่อนย้ายไป tests/fixtures/legacy-provider-sdk เพื่อคง Regression Test โดยไม่นับเป็นตัวอย่าง v4
