# Portable Doctor — v4

ตัวตรวจ Portable รุ่นใหม่ทำงานแบบอ่านอย่างเดียวและรองรับ **เฉพาะ .vwmodel v4** ตรวจได้ว่า Python Portable, uv Offline Installer, MakHam v4 เริ่มต้น และ Runtime ของแพ็กเกจที่ติดตั้งอยู่พร้อมใช้งานหรือไม่

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -X utf8 -m voxweavetts.portable_doctor --root dist\VoxWeaveTTS-v4-validation --json --strict
```

สถานะ `needs-attention` อาจหมายถึง Runtime ไม่ครบ โมเดลเริ่มต้นไม่พร้อม หรือมีโฟลเดอร์รุ่นเก่าค้างอยู่ภายใน Stage โดย **ตัวตรวจไม่ลบไฟล์ของผู้ใช้** และไม่ติดตั้งโมเดลเอง

หากแพ็กเกจมีปัญหา ผู้ใช้สามารถถอนติดตั้งแล้วติดตั้งไฟล์ .vwmodel v4 เดิมอีกครั้ง ไม่มีระบบซ่อมแยก ไม่ติดต่อเซิร์ฟเวอร์หรือ PyPI

[สร้าง Portable](PORTABLE.md) · [ผลทดสอบ v4](V4_ALL_MODEL_QA_TH.md)
