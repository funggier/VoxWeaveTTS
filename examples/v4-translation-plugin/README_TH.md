# v4: ต้นแบบ Worker แปลภาษาที่ไม่ต้องอัปเดต Core

plugin/worker.py เป็นตัวอย่าง Offline M2M100 Translation Worker แบบ JSON Lines ขาเข้าเป็นข้อความ, ภาษาต้นทาง/ปลายทาง และรหัสคำขอ ขาออกเป็นข้อความที่แปลแล้ว

แพ็กเกจชนิด translation ใช้ engine.operation = translate, engine.languages เป็นรายการภาษา และ runtime เป็น Python 3.11 + Wheel ที่แนบครบตามมาตรฐาน v4; ไม่มี sample_rate/voices เพราะไม่สร้างเสียง

สำหรับโมเดลแปลภาษาจริงให้เตรียม manifest, plugin/worker.py, น้ำหนักโมเดล Safetensors และ Wheel ที่มีสิทธิ์แจกจ่าย แล้วสร้างด้วย scripts/build_vwmodel_v4.py ไม่จำเป็นต้องใช้ไฟล์หรือโค้ด v3

หมายเหตุ: M2M100 มีขนาดใหญ่และต้องใช้ Windows RAM/Commit มาก การทดสอบติดตั้งออฟไลน์ผ่านไม่ได้ยืนยันคุณภาพการแปลทุกประโยค
