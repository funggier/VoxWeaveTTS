# Model-neutral Core — v4

เป้าหมายของ VoxWeaveTTS คือให้ทุกโมเดลมี Worker ของตัวเองในแพ็กเกจ Universal v4 และไม่ต้องเพิ่มชื่อโมเดลใหม่ใน Core เมื่อผู้ใช้เพิ่มเสียงหรือ Engine

Core รู้จักเพียง Metadata ของโมเดล (ชนิด TTS/Translation, ภาษา, เสียง, Sample Rate, Rights) และ Worker Protocol v1 เท่านั้น ไม่มีการ Import โมดูลเฉพาะ MakHam/Kokoro/Vachana/Wayu หรือการรองรับแพ็กเกจ v3

รองรับ Python 3.11 พร้อม Wheel ออฟไลน์ที่มากับแพ็กเกจ หรือ Native Worker .exe ในไฟล์เดียว โปรแกรมหลักจัดการ Queue, Voice Controls, Overlay และ API ตามเดิม

[Universal v4](UNIVERSAL_VWMODEL_V4_TH.md) · [Architecture](ARCHITECTURE.md)
