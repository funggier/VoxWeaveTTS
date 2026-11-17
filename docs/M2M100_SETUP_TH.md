# M2M100 418M — วิธีติดตั้งและแก้ปัญหา (VoxWeaveTTS v0.9.5)

**สถานะ:** โมเดลทดลอง (Experimental) ไม่รับรองความแม่นยำการแปลหรือความเหมาะสมสำหรับ Live ทุกกรณี

## ถ้าติดตั้ง .vwmodel ไม่สำเร็จ

M2M100 เป็น **AI/Translation Model Package** แม้จะใช้นามสกุล `.vwmodel` เหมือน TTS แต่ Manifest คนละประเภท (`voxweavetts.ai-model-package` กับ `voxweavetts.model-package`)

Source ที่แก้ไขหลัง v0.9.4 รองรับการเลือก M2M100 ผ่าน **Model Package Manager หลักหรือ AI/Translation Model Packages** โดยอ่านชนิด Manifest ก่อนส่งเข้าตัวติดตั้งที่ถูกต้อง; รุ่น v0.9.4 ที่เผยแพร่ก่อนการแก้ไขนี้ต้องใช้เมนู **ตั้งค่า → AI / Translation → AI/Translation Model Packages → ติดตั้ง AI Model Package** เท่านั้น

- ไฟล์แพ็กเกจ: `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` ดาวน์โหลดแยกจาก Release
- หลังเลือกไฟล์ การตรวจ SHA-256 และแตกข้อมูลน้ำหนักจริง **1,935,681,888 ไบต์** อาจใช้เวลานาน เพราะต้องตรวจไฟล์เต็มและเขียนลงดิสก์แบบปลอดภัย ให้รอจนหน้าโปรแกรมแจ้งผล
- ตัวติดตั้งจะวางใน `models/ai/packages/m2m100-418m/1.0.0/` โดยไม่ลบโมเดลรุ่นเก่า `models/ai/m2m100_418m/` หรือ Settings/Presets เดิม
- ถ้าเห็น **already installed** แปลว่ามีแพ็กเกจรุ่นเดียวกันติดตั้งแล้ว ให้กดรีเฟรชรายการ ไม่จำเป็นต้องติดตั้งซ้ำ
- ต้องมีพื้นที่ว่างเพิ่มเติมอย่างน้อยประมาณ 2 GB สำหรับไฟล์ที่แตกออกมา (มากกว่านี้สำหรับ Runtime/Cache)

## ติดตั้ง PyTorch/Transformers Runtime แบบแยก Environment

**การติดตั้งน้ำหนักโมเดลสำเร็จ ไม่ได้หมายความว่า Runtime พร้อมแปลภาษาแล้ว** รุ่น Portable ไม่รวม Torch/Transformers ใน ZIP หลัก เพื่อไม่ให้ไปรบกวน NumPy/ONNX Runtime ของโมเดล TTS

ใน Source ที่แก้ไขหลัง v0.9.4:

1. เปิด **ตั้งค่า → AI / Translation**
2. กด **ติดตั้ง / ซ่อม Runtime M2M100 (แยก Environment · uv)** แล้วดูสถานะผ่านปุ่ม **ตรวจสถานะ Runtime M2M100**
3. ต้องมี `uv` ใน PATH และอินเทอร์เน็ตครั้งแรกสำหรับติดตั้ง Dependencies ที่กำหนดไว้ใน `scripts/ai-dependencies/m2m100.txt`
4. Runtime จะอยู่ที่ `runtime/ai-envs/m2m100/`, Log ที่ `logs/ai-runtime/install-m2m100.log` และ Cache ภายใน `cache/` ของโปรแกรม ไม่แตะ Ollama หรือ Python Environment ของโมเดลเสียง
5. เมื่อ Runtime พร้อม เลือก **Engine: M2M100**, เลือกแพ็กเกจ `m2m100-418m@1.0.0` และกำหนดภาษาต้นทาง/ปลายทางให้ชัดเจน กดบันทึก Settings แล้วทดสอบข้อความก่อนใช้งานจริง

หากต้องการติดตั้งแบบคำสั่ง ให้รันในโฟลเดอร์ VoxWeaveTTS:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-M2M100Runtime.ps1
```

Python 3.11 ของ Portable สามารถเรียก M2M100 ผ่าน Worker IPC แบบ Offline ที่ใช้ Process แยก โมเดลที่โหลดแล้วถูกเก็บไว้ใน Worker เพื่อไม่ต้องโหลดใหม่ทุกข้อความ และ Stop ของ VoxWeaveTTS จะจัดการ Process ที่เป็นเจ้าของเองอย่างปลอดภัย

หากย้ายทั้งโฟลเดอร์ Portable หลังติดตั้ง Runtime ไปคนละ Drive ให้ใช้ Install/Repair Runtime อีกครั้ง เนื่องจาก Windows virtual environment อาจจดจำที่อยู่เดิม

## ข้อจำกัดการแปลและสิทธิ์

- Upstream: [facebook/m2m100_418M](https://huggingface.co/facebook/m2m100_418M) ที่ Revision `1fa802356610a66e78d152c9f4a16206f88315e5`
- Official safetensors SHA-256: `c061a21eec15453944783ceb4a13a216477dd4765c98fac10811818adf994968`
- การใช้โมเดล M2M100 ส่งเฉพาะข้อมูลการแปล (ข้อความ, รหัสภาษาต้นทาง/ปลายทาง และ Model ID ที่ตรวจสอบแล้ว) ไม่ส่ง Prompt, คำสั่งจากแชท, API Keys หรือข้อมูลส่วนตัวไปให้โมเดลหรือคำสั่งติดตั้ง
- M2M100 ไม่ใช่ LLM ไม่เข้าใจ Priority/Custom Prompt และการแปลออกมาเป็นภาษาเป้าหมาย **ไม่ใช่หลักฐานว่าความหมายถูกต้อง**
- ทดลองจริงพบว่าแปลอังกฤษ→ไทยข้อความสั้น `Good morning.` ออกมาเป็น `ดีเช้า` ซึ่งฟังไม่เป็นธรรมชาติ จึงควรทดสอบและตรวจคุณภาพก่อนเปิดอ่านแชท Live
- ยังคง Pipeline กฎเฉพาะโหมด → กฎส่วนกลางก่อน AI → แปล → กฎส่วนกลางหลัง AI → TTS และการแยกข้อความตามภาษาหลังแปลได้ตาม Settings
- หากเลือกภาษาเป้าหมาย **ไม่ระบุ** M2M100 จะข้ามการแปลตามที่กำหนด

**การเผยแพร่:** แพ็กเกจน้ำหนัก M2M100 เป็น Asset แยกใน Release ไม่รวมใน Portable ZIP หลัก; การดาวน์โหลดโมเดลไม่ได้ให้สิทธิ์รันโค้ดใด ๆ จากภายใน .vwmodel
