# เสียงส่วนตัว [NC / NonCommercial] — Wayu Paxa Edge

เวอร์ชันฟีเจอร์: ต่อยอดจาก VoxWeaveTTS v0.9.2 (ติดตั้งในเครื่องนักพัฒนา)

## จุดประสงค์และสถานะสิทธิ์

**[NC / NonCommercial] Wayu Paxa Edge — ไทย/อังกฤษ 12 เสียง** เป็นตัวเลือกสำหรับอ่านข้อความ/คอมเมนต์ YouTube ฟังเองส่วนตัว ไม่ใช้เป็น Engine หลักสำหรับแพ็กเกจเชิงพาณิชย์

- โค้ด Inference: [wayu-research/wayu-tts-inference](https://github.com/wayu-research/wayu-tts-inference) — **Apache-2.0**; ตรวจที่ revision `07ab898d516649313926f0b843b809a962f993ad`
- **น้ำหนักโมเดลและ voice styles:** [wayu-ai/wayu-paxa-tts-edge](https://huggingface.co/wayu-ai/wayu-paxa-tts-edge) — **CC BY-NC 4.0**, revision `8196688df56a8d08ccfa186505343adff412ab6b`
- แม้โค้ดจะอนุญาตเชิงพาณิชย์ แต่ **สิทธิ์น้ำหนักโมเดลเป็น NonCommercial** การใช้เชิงพาณิชย์ต้องได้รับสิทธิ์เพิ่มเติมอย่างเหมาะสม
- ข้อมูลเสียงต้นทางและสิทธิ์บุคคลยังไม่ได้รับการตรวจสอบโดยอิสระ จึงกำหนดสถานะ `hold`; ไม่ใช่ Commercial-Cleared
- **ไม่อัปโหลด** น้ำหนัก `model.pth`, `voices/*.pt` หรือเสียงผู้ใช้ไปยัง Public GitHub/Portable ZIP โดยอัตโนมัติ
- ชื่อ Engine ที่แสดงในทุกหน้าที่ใช้รายการ Engine และภาษาเริ่มด้วย **`[NC / NonCommercial]`**; หากติดตั้งแพ็กเกจ `.vwmodel` อื่นที่ SPDX เป็น `CC-BY-NC-...` จะติดป้าย `[NC / NonCommercial]` ในชื่อที่แสดงด้วย

## ติดตั้งในเครื่องสำหรับผู้ใช้ที่ยอมรับ License เท่านั้น

ใช้ Python 3.11 ใน Virtual Environment ของโปรเจกต์ (หรือ Environment อื่นที่ติดตั้ง Dependency เหล่านี้):

```powershell
.venv\Scripts\python.exe -m pip install "git+https://github.com/wayu-research/wayu-tts-inference.git@07ab898d516649313926f0b843b809a962f993ad"
.venv\Scripts\python.exe -m pip install "numpy==2.2.6" "scikit-learn==1.7.2" "pandas==2.3.3" "pyopenjtalk==0.4.1"
.venv\Scripts\python.exe -m spacy download en_core_web_sm
```

ดาวน์โหลดจาก Hugging Face หลังอ่าน Model Card และ CC BY-NC 4.0:

```powershell
.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('wayu-ai/wayu-paxa-tts-edge', revision='8196688df56a8d08ccfa186505343adff412ab6b', allow_patterns=['config.json','model.pth','voices/*.pt','README.md'], local_dir='models/personal/wayu-paxa-tts-edge')"
```

**ข้อควรทราบ Dependency:** ใน Environment ทดสอบนี้ `tltk==1.11` ระบุ `scikit-learn~=1.2.0` แต่ `kokoro-onnx==0.6.0` ต้องการ NumPy 2.x ซึ่งทำให้ scikit-learn 1.2 ที่คอมไพล์มากับ NumPy เก่าไม่สามารถนำมาใช้ร่วมกันได้ จึงต้องใช้ scikit-learn 1.7.2 ที่ ABI เข้ากันได้กับ NumPy 2.2.6; `pip check` จะแจ้งความขัดแย้งของ metadata สำหรับ tltk แม้จะสังเคราะห์เสียงได้ในการทดสอบ ควรแยก Environment สำหรับรุ่นเผยแพร่จริงและทดสอบความเข้ากันได้อีกครั้ง

ต้องมี:

```text
models/personal/wayu-paxa-tts-edge/
  config.json
  model.pth  (SHA-256 eb26ac6f7da4c651389b28793d0ab59be8fa7e3e7cc5d350278b2a8d0a4d7370)
  voices/
    f_teen_bright.pt
    f_young_bright.pt
    f_young_clear.pt
    f_young_warm.pt
    f_mid_clear.pt
    f_mid_warm.pt
    f_elderly_soft.pt
    f_elderly_low.pt
    m_teen_bright.pt
    m_young_clear.pt
    m_mid_warm.pt
    m_elderly_deep.pt
```

ก่อนใช้งานจริงให้ติดตั้งแพ็กเกจภาษาอังกฤษ spaCy `en_core_web_sm` ตามคำสั่งข้างต้นด้วย เพราะ upstream G2P อาจพยายามดาวน์โหลดเองเมื่อขาดแพ็กเกจนี้; ตัว Adapter จะตรวจความพร้อมและปฏิเสธการสังเคราะห์เมื่อขาด Dependency เพื่อไม่ให้เริ่มดาวน์โหลดจากการรับคอมเมนต์ ชุดโมเดลถูกโหลดจากไฟล์ **Local Only** และอยู่ใน `models/` ซึ่งถูก `.gitignore` ไว้

## การใช้และข้อจำกัดด้านเสียง

เปิด VoxWeaveTTS แล้วเลือก Engine **[NC / NonCommercial] Wayu Paxa Edge — ไทย/อังกฤษ 12 เสียง** จากเมนูของโหมด เช่น **YouTube LIVE**, เลือกเสียง แล้วอ่านข้อความได้ตามคิวเดิม เสียง WAV และ Subtitle/Event ใช้ Pipeline ปกติ

เสียงที่เน้นความมีชีวิตชีวา: `f_teen_bright`, `f_young_bright`, `m_teen_bright`. เสียงนุ่มฟังสบาย: `f_young_warm`, `f_mid_warm`, `m_mid_warm`. เสียงเล่านิ่ง: `f_young_clear`, `m_young_clear`, `m_elderly_deep`.

โมเดลนี้เป็น **fixed-voice TTS** ไม่ใช่โมเดลสั่งอารมณ์ด้วยข้อความ (เช่น แสดงความโกรธ/เศร้า) ได้โดยตรง ความแตกต่างมาจากเสียงและลักษณะการอ่านที่ฝึกไว้ ไม่รับประกันการถ่ายทอดอารมณ์อย่างละเอียด การเลือกเสียง/ความเร็ว/ระดับเสียงหลังสังเคราะห์อาจช่วยให้ฟังลื่นไหลขึ้น

**ข้อจำกัด Portable:** Environment ที่ติดตั้ง Wayu และน้ำหนัก NC ไม่ได้บันเดิลรวมใน Portable ZIP หลัก ผู้ใช้เครื่องอื่นต้องติดตั้ง Dependency และน้ำหนัก NC แยกพร้อมยอมรับ License

การใช้โมเดลอ่านข้อความจากแพลตฟอร์มอื่นไม่ได้ให้สิทธิ์นำเสียงของบุคคล หรือข้อความที่มีลิขสิทธิ์ไปเผยแพร่โดยอัตโนมัติ
