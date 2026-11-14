# M2M100 418M (ทดลอง) — เตรียมโมเดลใน VoxWeaveTTS

สถานะ v0.6.0: **EXPERIMENTAL / ต้องทดสอบความหมายก่อนใช้จริง**; ไม่ใช่โมเดลแปลที่ผ่านการรับรองคุณภาพ
ไม่มีปุ่มดาวน์โหลดหรือติดตั้งโมเดล AI อัตโนมัติใน UI และไม่ได้รวมโมเดล M2M100 / Torch Runtime ใน Portable หลัก

## การทำงานและสิทธิ์

- Built-in **AI Engine Adapter** เป็นโค้ดที่ตรวจสอบได้ในแอป ไม่ได้เรียกโค้ด Python จากไฟล์โมเดล
- โมเดลต้นทาง: [facebook/m2m100_418M](https://huggingface.co/facebook/m2m100_418M) / upstream model card ระบุ MIT (ไม่ได้ตรวจสอบสิทธิ์ชุดข้อมูลทั้งหมดโดยอิสระ)
- แพ็กเกจที่ใช้ต้องเป็น **safetensors** และ tokenizer/config จากต้นทางที่น่าเชื่อถือ ไม่โหลด pickle `.bin` หรือไฟล์ executable จากโมเดล
- ทดสอบด้วย official safetensors revision `1fa802356610a66e78d152c9f4a16206f88315e5`; น้ำหนัก `model.safetensors` ขนาด 1,935,681,888 bytes, SHA-256 `c061a21eec15453944783ceb4a13a216477dd4765c98fac10811818adf994968`
- การแปลจริง 3 ประโยค: ภาษาไทย→อังกฤษเข้าใจความหมายถูกในตัวอย่าง แต่ภาษาอังกฤษ→ไทย และอังกฤษ→ญี่ปุ่น **ผิดความหมาย** แม้อักษรปลายทางถูก ดังนั้นสถานะคือ *Inference works; translation quality not qualified* ไม่ใช่ production-ready

## วิธีใช้โมเดลที่มีอยู่แล้ว

1. คัดลอกไฟล์โมเดล **ที่ผู้ใช้ดาวน์โหลดและตรวจสอบแหล่งที่มาเอง** ไปไว้ในโฟลเดอร์ที่เขียนได้ `models/ai/m2m100_418m/` ภายใน VoxWeaveTTS:
   - `model.safetensors`
   - `config.json`
   - `vocab.json`
   - `sentencepiece.bpe.model`
   - แนะนำ `tokenizer_config.json`, `special_tokens_map.json`, `generation_config.json`
2. ติดตั้ง Python dependencies เสริม **แยกจาก Portable หลัก** ลงใน Python Environment ที่ใช้รันโปรแกรมจริง: `torch>=2.3,<2.9`, `transformers>=4.45,<5`, `sentencepiece`, `safetensors`. ตัวอย่างสำหรับผู้พัฒนา ถ้ามี `uv` อยู่แล้ว:

   ```powershell
   uv pip install --python .\.venv\Scripts\python.exe 'torch>=2.3,<2.9' 'transformers>=4.45,<5' sentencepiece safetensors
   ```

   สำหรับ Portable ที่แตก ZIP แล้ว: หากคุณติดตั้ง `uv` ด้วยตัวเอง สามารถเปลี่ยนเป้าหมาย `--python` เป็น `.\runtime\python\python.exe` ได้ (ขึ้นกับสิทธิ์เขียนโฟลเดอร์); **ไม่ต้องทำขั้นตอนนี้เพื่อใช้งาน Ollama หรือ TTS MakHam ใน ZIP**
3. รีสตาร์ทโปรแกรมแล้วเปิด Settings → AI Processing → เลือก Engine `M2M100` และเลือกภาษาต้นทาง/ปลายทางให้ชัดเจน
4. ถ้าเลือก **ไม่ระบุภาษา** M2M100 จะข้ามการแปลโดยทันที ไม่ใช้ Prompt และไม่โหลดโมเดล
5. ใช้ช่องทดลองข้อความก่อนใช้กับ Live; M2M100 ไม่รองรับ Priority Instructions, Custom Prompt หรือ AI Tool Calling

## ตรวจสอบสถานะด้วยเครื่องจริง

Run จาก Environment ที่มี optional dependencies:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -u .\tests\verify_m2m100.py
```

สคริปต์นี้จะไม่ดาวน์โหลดโมเดลและไม่แก้ Settings; ตรวจ SHA-256 และเกณฑ์เชิงความหมาย 3 ตัวอย่าง ข้อผิดพลาดด้านความหมายจะทำให้ exit code เป็น 1 ไม่ควรนับว่า PASS เพียงเพราะ output มีอักษรภาษาที่ต้องการ

**สำคัญ:** แอปไม่เปิดไฟล์มั่วทั่วไดรฟ์ตามข้อความผู้ชม ไม่ดาวน์โหลด/ติดตั้งโมเดลเมื่อพิมพ์ชื่อ และ Tool Calling จะเพิ่มในรุ่นถัดไปหลัง v0.6.0 เท่านั้น