# v4: ต้นแบบ Worker แปลภาษาที่ไม่ต้องอัปเดต Core

plugin/worker.py เป็นตัวอย่าง Offline M2M100 Translation Worker แบบ JSON Lines ขาเข้าเป็นข้อความ, ภาษาต้นทาง/ปลายทาง และรหัสคำขอ ขาออกเป็นข้อความที่แปลแล้ว

แพ็กเกจชนิด translation ใช้ engine.operation = translate, engine.languages เป็นรายการภาษา และ runtime เป็น Python 3.11 + Wheel ที่แนบครบตามมาตรฐาน v4; ไม่มี sample_rate/voices เพราะไม่สร้างเสียง

ตัวอย่างการสร้างแพ็กเกจ M2M100 จริงพร้อมโมเดล Safetensors และ Dependencies จากไฟล์เก่าอยู่ใน scripts/convert_all_models_to_v4.py

หมายเหตุ: M2M100 มีขนาดใหญ่และต้องใช้ Windows RAM/Commit มาก การทดสอบติดตั้งออฟไลน์ผ่านไม่ได้ยืนยันคุณภาพการแปลทุกประโยค
