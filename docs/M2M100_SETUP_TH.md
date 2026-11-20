# M2M100 Translation — Universal v4

M2M100 418M เป็นแพ็กเกจ **Translation .vwmodel v4** แยกจาก TTS Engine ทั้งหมด มาพร้อมโมเดล Safetensors, Tokenizer, Python Worker และ Offline Dependencies ที่จำเป็น

ผู้ใช้เลือกไฟล์ .vwmodel v4 จากหน้าจัดการ Model Packages แล้วกดติดตั้งครั้งเดียว โปรแกรมจัดการ Python 3.11 และ Runtime แยกให้เอง ไม่ต้องเชื่อมต่อ PyPI, Ollama หรือ Hugging Face เพื่อโหลดข้อมูลเพิ่มขณะใช้งาน

Worker รับข้อความและภาษาต้นทาง/ปลายทางผ่าน JSON Lines และส่งข้อความแปลกลับ Core ตามระบบแปลภาษาเดิม ข้อความภายนอกเป็นข้อมูลเท่านั้น ไม่ใช่คำสั่งให้ AI

**QA:** แปล EN→TH และ TH→EN สำเร็จ แต่คุณภาพบางประโยคยังไม่เป็นธรรมชาติ และต้องมี Windows RAM/Commit เพียงพอสำหรับ PyTorch

ไฟล์โมเดล QA v4 ยังไม่ผ่านการตรวจสิทธิ์ Redistribute ครบ จึงไม่ได้เผยแพร่เป็น Public Release

[คู่มือ v4](UNIVERSAL_VWMODEL_V4_TH.md) · [ผล QA](V4_ALL_MODEL_QA_TH.md)
