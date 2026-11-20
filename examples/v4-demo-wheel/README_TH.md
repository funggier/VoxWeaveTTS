# v4: แพ็กเกจที่มี Python Wheel ใหม่ของตัวเอง

ตัวอย่างนี้พิสูจน์ว่า VoxWeaveTTS ไม่จำเป็นต้องรู้ชื่อ Library หรือ SHA-256 ของ Wheel ใหม่ล่วงหน้า ผู้พัฒนาบรรจุ Wheel และ Worker ในไฟล์ .vwmodel v4 แล้ว Core จะสร้าง Runtime แยกแบบออฟไลน์

สร้างตัวอย่างด้วย:

~~~powershell
.\.venv\Scripts\python.exe -X utf8 scripts\qa_build_v4_wheel_example.py
~~~

โค้ดสำหรับสร้าง Wheel/Manifest อยู่ใน scripts/qa_build_v4_wheel_example.py โดยใช้ Worker ต้นฉบับที่ examples/v4-demo-tone/plugin/worker.py และแทรกการนำเข้า Library ชื่อ v4fixture ซึ่งสร้างขึ้นในเครื่อง

ผลลัพธ์อยู่ที่ cache/v4-qa-candidates/demo-wheel-plugin-format-v4.vwmodel (ตัวอย่าง QA ไม่ใช่ Release) การทดสอบสร้าง PCM16 เสียงโทน ไม่ใช่ TTS พูดได้

สำหรับผลิตภัณฑ์จริงให้บรรจุ Wheel ที่ตรวจสอบสิทธิ์และใช้งานได้จริงทั้งหมดเอง ไม่ใช้ตัวติดตั้งออนไลน์
