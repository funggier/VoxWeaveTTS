# ตัวอย่างสำหรับพัฒนา Model Package ของ VoxWeaveTTS v4

ตัวอย่างสำหรับสร้างส่วนเสริมใหม่ทั้งหมดในโฟลเดอร์นี้ใช้มาตรฐาน Universal .vwmodel v4 เท่านั้น

- v4-demo-tone: ตัวอย่าง Python Worker ขั้นพื้นฐานที่ไม่ต้องติดตั้ง Wheel
- v4-demo-wheel: ตัวอย่างสร้าง Python Wheel ใหม่ในเครื่อง พร้อมบรรจุให้ติดตั้งออฟไลน์
- v4-native-worker: ตัวอย่าง Native Worker .exe เขียนด้วย C#
- v4-model-plugin: Worker สำหรับเชื่อมต่อ TTS หลายสถาปัตยกรรมจากแพ็กเกจอิสระ
- v4-translation-plugin: Worker แปลภาษาด้วย Protocol v1 และ Offline Model

ตัวอย่างการสร้างเสียงโทนใช้พิสูจน์โครงสร้างเท่านั้น **ไม่ใช่โมเดล TTS ที่พูดจริง** ส่วน Worker ของโมเดลจริงต้องใช้น้ำหนักโมเดลและ Wheel ที่มีสิทธิ์แจกจ่ายครบก่อนทำ Public Release

ดูคู่มือ docs/UNIVERSAL_VWMODEL_V4_TH.md และตัวอย่างการประกอบโมเดลจริง scripts/convert_all_models_to_v4.py

ตัวอย่างระบบ Provider รุ่นก่อนย้ายไป tests/fixtures/legacy-provider-sdk เพื่อคง Regression Test โดยไม่นับเป็นตัวอย่าง v4
