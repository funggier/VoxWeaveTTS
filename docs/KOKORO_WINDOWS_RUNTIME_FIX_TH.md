# Kokoro Runtime บน Windows Portable — แก้ปัญหาติดตั้ง pyopenjtalk ไม่สำเร็จ

**สถานะ:** รวมการแก้ไขใน Release v0.10.3; **ยังไม่อยู่ใน ZIP รุ่นเก่า v0.10.2**

## อาการและสาเหตุ

ขณะติดตั้งหรือกู้คืน Runtime `kokoro · tts` ใน Portable ที่อยู่ในโฟลเดอร์หลายชั้น อาจเกิด:

- `Failed to build pyopenjtalk==0.4.1`
- `FileTracker : error FTK1011: could not create the new file tracking log file`
- CMake/MSBuild ไม่สามารถสร้างไฟล์ .tlog ภายในพาธ Cache ที่ยาวมากได้

Recipe ใน v0.10.2 ใช้ `misaki[ja]==0.9.4` ซึ่งดึง `pyopenjtalk` มาติดตั้งจาก Source บน Windows แทนการใช้ Wheel สำเร็จรูป จึงต้องคอมไพล์ C/C++ การย้ายโปรแกรมไปโฟลเดอร์ที่สั้นลงช่วยลดโอกาสพบปัญหา แต่ไม่ใช่การแก้สาเหตุที่ต้อง Build Native Package

## การแก้ไขใน Release v0.10.3

แก้เฉพาะ Recipe ที่โปรแกรมควบคุมเอง `scripts/engine-dependencies/kokoro.txt` เป็น:

- `kokoro-onnx==0.6.0`
- `onnxruntime==1.31.1`
- `numpy==2.2.6`
- `misaki[ja]==0.8.0`
- `unidic-lite==1.0.8`

Misaki 0.8.0 ใช้เส้นทาง Japanese G2P แบบ Cutlet/MeCab กับ UniDic Lite ซึ่งโปรเจกต์มีการรองรับเดิมแล้ว และไม่ต้องดึง `pyopenjtalk` เข้า Runtime นั้นโดยตรง อย่างไรก็ตาม รุ่น G2P 0.8.0 อาจมีรายละเอียดการออกเสียงหรือ Pitch Accent ต่างจาก 0.9.4; ไม่ใช่การรับรองคุณภาพการอ่านทุกประโยค

หลังอัปเดต Recipe ใน Portable ที่ใช้จริง หากการติดตั้งครั้งก่อนล้มเหลวและมี Python Env ไม่สมบูรณ์ ให้ใช้การติดตั้ง Kokoro ผ่าน **Engine Providers** พร้อมยืนยันเงื่อนไขของ Provider อีกครั้ง (โดยใช้ trusted recipe ที่แก้แล้ว) แทน Repair แบบ Offline ซึ่งใช้ได้เฉพาะเมื่อมี Wheel Cache ที่ครบและมี Marker ที่ถูกต้อง ห้ามแก้ไขรายการ Dependencies จากข้อความแชทหรือไฟล์โมเดล

## ผลการทดสอบที่ยืนยัน

- ติดตั้ง Kokoro Runtime แยกใน Windows 10/Python 3.11 ตาม Recipe ใหม่: ผ่าน, 19 Dependencies, `uv pip check` ผ่าน
- ตรวจว่าไม่มี `pyopenjtalk` ใน Environment ที่สร้างใหม่: ผ่าน
- ทดสอบ `misaki.ja.JAG2P` กับข้อความภาษาญี่ปุ่นจริง: ผ่าน
- อัปเดต Recipe และติดตั้ง Runtime ที่เครื่องผู้ใช้ (Portable v0.10.2 บนพอร์ต 8775): ผ่าน; Runtime Registry รายงาน `ready`
- ใช้โมเดล Kokoro Universal v2 ที่ติดตั้งจริง สร้าง WAV ผ่านทั้งภาษาอังกฤษ (`af_heart`) และภาษาญี่ปุ่น (`jf_alpha`) ที่ 24,000 Hz: ผ่าน

ไม่ลบข้อมูลโมเดล/การตั้งค่าผู้ใช้ ไม่รวม Wheelhouse Candidate ของ Kokoro ใน Release และการยินยอมติดตั้งไม่ได้มอบสิทธิ์แจกจ่าย Dependencies
