# M2M100 Native v2 — ตรวจการแปลจริงผ่าน Isolated Worker (Phase E)

**สถานะ:** รวมการปรับปรุงและเครื่องมือตรวจใน Release `v0.10.2`; ผลวัดอ้างอิงเฉพาะเครื่องพัฒนา

## สิ่งที่ตรวจพบ

M2M100 418M เคยมีสถานะติดตั้งโมเดล/Runtime แล้ว แต่การอ่านคำแปลจริงด้วย Worker ใช้เวลานานจนหมดเวลารอ โดยผลทดสอบวันที่ 18 พฤศจิกายน 2026 บน Windows 10 x64 เครื่องพัฒนา:

- โมเดล Native `.vwmodel v2` มี `model.safetensors` ต้นฉบับขนาดประมาณ **1.94 GB** และมีพารามิเตอร์ใน PyTorch จำนวน **483,905,536**; ใช้ CPU เท่านั้น
- รอบก่อนแก้: Python Worker ใช้หน่วยความจำที่จอง (Private Bytes) ราว **4.6 GiB** และ Worker IPC ไม่ส่งคำแปลภายใน **165 วินาที** แม้ตรวจ RAM และ Commit ผ่านเกณฑ์ขั้นต่ำ
- ตรวจแยก Model Load/Generate พบว่าการโหลดโมเดลใช้ราว **3 วินาที** เท่านั้น แต่ระหว่าง Generation ค่า Default ของ CPU/Thread Scheduling ทำให้ระยะเวลาผันผวนมาก
- รอบปรับ 2 CPU Threads: ทดลอง Greedy (1 Beam) และ Beam Search 2/4 Beams; เมื่อ OS File Cache อุ่นขึ้น การสร้างคำแปลสั้น ๆ ใช้เวลาต่ำกว่า 1 วินาทีต่อข้อความในสคริปต์ Profiling โดยยังคงใช้ 4 Beams ได้
- การทดสอบเต็มผ่าน JSON IPC Worker ที่โปรแกรมใช้จริง: `Good morning.` (en→th) เป็น `สวัสดีเช้า` ครั้งแรก **3.55–3.86 วินาที**; `ขอบคุณครับ` (th→en) เป็น `thank you.` ครั้งต่อมา **0.34–0.39 วินาที** โดยใช้ Worker เดิม

- **ทดสอบ Portable จากศูนย์ในโฟลเดอร์แยก:** คัดลอก Portable Stage ใหม่ → ติดตั้งไฟล์ `.vwmodel v2` M2M100 โดยตรวจ Manifest/Hash → ติดตั้ง Runtime จาก Verified Offline Wheelhouse 25 Wheels โดยไม่มี `uv` จาก Windows PATH → รัน `m2m_smoke.verify` แปล en↔th สำเร็จใน **14.359 วินาที** → ย้ายโฟลเดอร์ → ระบบตรวจพบ `relocated` → ซ่อม Runtime จาก Verified Wheelhouse สำเร็จ → แปลสองภาษาซ้ำหลังซ่อมใน **23.437 วินาที** (รวมเริ่ม Worker และโหลดโมเดลใหม่) โดยไม่ใช้ Runtime หรือข้อมูลผู้ใช้จากโฟลเดอร์โปรเจกต์เดิม

**ข้อจำกัดสำคัญ:** `สวัสดีเช้า` ยังไม่ใช่สำนวนไทยที่เป็นธรรมชาติที่สุด การทดสอบนี้พิสูจน์ว่าโหลดและประมวลผลสำเร็จ ไม่ได้พิสูจน์ความถูกต้องของคำแปลทุกภาษา การเปรียบเทียบเวลาเป็นผลเฉพาะเครื่องและขึ้นกับ Windows Pagefile, CPU, RAM, Disk File Cache และข้อความที่ใช้

## การแก้ใน Source

- จำกัดเฉพาะ **M2M100 Isolated Worker** ให้ใช้ `torch.set_num_threads(2)`, inter-op 1 thread, `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2` และปิด Autograd เพื่อไม่ให้ CPU Threads แย่งทรัพยากรกันมากเกินไป ไม่เปลี่ยน Threads ของ TTS/Ollama หรือโปรแกรมหลัก
- คง **Beam Search 4** เพื่อรักษาวิธีแปลเดิม และตั้ง `early_stopping=False` เนื่องจาก `True` ทำให้ประโยคทดสอบบางตัวตัดสั้นเกินไป
- Model Loader ยังใช้ `local_files_only=True` + `use_safetensors=True` และถูกโหลดภายใน Worker เท่านั้น ไม่โหลด PyTorch เข้า Core
- ตั้ง `PYTHONNOUSERSITE=1`, Offline Env และ UTF-8 ของ Worker ให้ชัดเจน
- เพิ่มเกณฑ์ RAM/Commit ล่วงหน้า: ต้องมี **Commit ว่างอย่างน้อย 6 GiB** และ RAM ว่างอย่างน้อย 2 GiB บน Windows ก่อนเริ่ม Worker เพื่อป้องกัน OSError 1455; เป็นเกณฑ์อนุรักษ์นิยมไม่ใช่ข้อรับประกันว่าโมเดลจะรันสำเร็จ
- **ไม่** หยุด Ollama, ไม่แก้ Pagefile, ไม่ติดตั้ง Dependencies, ไม่ดาวน์โหลดโมเดล และไม่ลบข้อมูลผู้ใช้ระหว่างการปรับและทดสอบนี้

## วิธีทดสอบหลังติดตั้งบนเครื่องอื่น

ใช้ Source/Portable **ที่มีการแก้ Phase E นี้** และติดตั้ง M2M100 Native v2 กับ Runtime โดยเลือก Verified Wheelhouse ที่ถูกต้องมาก่อน จากโฟลเดอร์ Portable เปิด PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Check-Portable.ps1

# ทดสอบสังเคราะห์คำแปลจริงสองทิศทาง; เรียกเฉพาะเมื่อผู้ใช้สั่ง
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Verify-M2M100Runtime.ps1

# รายงาน JSON (ข้อความ Unicode จะแปลงเป็น Escape เพื่อรองรับ Console ต่าง ๆ)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Verify-M2M100Runtime.ps1 -Json

# จำกัดเวลารอของแต่ละคำแปล (15–180 วินาที)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Verify-M2M100Runtime.ps1 -TimeoutSeconds 60
```

ตัวตรวจทำงานด้วย Python ภายใน Portable ไม่เรียก Python จาก Windows PATH ใช้ข้อความที่ฝังใน Source เพียง `Good morning.` และ `ขอบคุณครับ` ไม่อ่าน Secret/Live Chat/Prompt/Settings ส่วนตัว ส่งผลผ่าน Isolated Worker มาตรฐาน และปิด Worker เมื่อจบหรือเกิดข้อผิดพลาด ทั้งสองคำแปลต้องไม่ว่างจึงจะคืน Exit Code 0

**ข้อควรระวัง:** ตัวตรวจนี้ **ประมวลผลโมเดลจริง** จึงใช้ CPU/หน่วยความจำและเขียน Runtime Log ภายในโปรแกรม ต่างจาก Portable Doctor ซึ่งเป็น Read-only Metadata Inspection โดยผล JSON จะมีคำแปลต้นแบบและเวลาที่ใช้เพื่อช่วยวิเคราะห์ความพร้อม ไม่ถือเป็นผลตรวจคุณภาพ/สิทธิ์โมเดลเชิงพาณิชย์

## การทดสอบ Portable สะอาดแบบครบวงจร (เฉพาะผู้พัฒนา)

หลังสร้าง Stage ด้วย `scripts/Build-Portable-V2.ps1 -SkipZip` และเตรียมไฟล์ Release Model / Verified Wheelhouse ตามโครงสร้าง `dist/` สามารถสั่ง:

```powershell
.\.venv\Scripts\python.exe scripts\verify_portable_m2m_e2e.py
```

เครื่องมือทดสอบนี้ **ไม่รวมใน Portable ที่แจกจ่าย** และต้องมีพื้นที่ดิสก์หลาย GiB ว่างสำหรับคัดลอกไฟล์โมเดลและ Runtime ใหม่ การทดสอบจำกัด `PATH` ไม่ใช้ uv ของ Windows, ติดตั้ง Native v2 และ M2M100 Runtime แบบ Offline, แปลจริงสองภาษา, ย้ายโฟลเดอร์, ซ่อม Runtime จาก Verified Wheelhouse และแปลซ้ำหลังซ่อม

หลังทำงานจะลบ **เฉพาะโฟลเดอร์ทดสอบที่สร้างใหม่ใน `cache/temp/m2m100-fresh-portable-*`** เท่านั้น พร้อม Retry เมื่อ Windows หรือ Antivirus ยังถือไฟล์ `model.safetensors` หากขั้นตอนทั้งหมดผ่านแต่ลบโฟลเดอร์ชั่วคราวไม่ได้ จะระบุว่าเป็น *Cleanup Error* แยกจากความผิดพลาดในการติดตั้ง/แปล และไม่พยายามลบโมเดลต้นทางหรือโฟลเดอร์อื่น

**ผลทดสอบจริง 18 พฤศจิกายน 2026:** ทดสอบจาก Stage ใหม่บน Windows เครื่องพัฒนาด้วย M2M100 1.94 GB และ Verified Wheelhouse 25 Wheels: ติดตั้ง Native v2, ติดตั้ง Runtime Offline, แปลจริง en↔th, ย้ายโฟลเดอร์, ตรวจพบ Runtime `relocated`, ซ่อมจาก Wheelhouse, แปลจริงซ้ำ และล้างโฟลเดอร์ชั่วคราว **สำเร็จทุกขั้นตอน (Exit Code 0)** ไม่ได้ทดสอบบนคอมพิวเตอร์ Windows อีกเครื่อง

M2M100 Worker จะปิดช่องรับคำสั่งเพื่อให้ Python จบตามปกติ ก่อนใช้การปิดแบบบังคับเมื่อค้างหรือหมดเวลา ช่วยลดการถือครองไฟล์น้ำหนักโมเดลหลังเลิกใช้งาน ส่วนคำสั่งตรวจ `Verify-M2M100Runtime.ps1` เพิ่มการปฏิเสธกรณีแปลแล้วได้ข้อความเดิม หรือใช้อักษรไม่ตรงภาษาปลายทางที่เลือก โดยการตรวจนี้ยังไม่ใช่การประเมินความถูกต้องตามความหมาย

## งานถัดไป

ทดสอบแปลประโยคหลายภาษา/หลายความยาวด้วยผู้ประเมินภาษา, ตรวจคุณภาพข้อมูลเสียงเมื่อส่งเข้า Multilingual TTS, ทดสอบบน Windows อีกเครื่องจริงที่ไม่เคยติดตั้ง Runtime, และตรวจว่าค่าตั้งต้นสำหรับ CPU รุ่นอื่นเหมาะสมเพียงใด
