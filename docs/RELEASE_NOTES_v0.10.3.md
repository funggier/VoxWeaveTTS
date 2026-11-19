# VoxWeaveTTS v0.10.3 — แก้ปัญหาซ่อม Kokoro Runtime บน Windows

**Windows 10/11 x64 · Portable Python 3.11 · Bugfix จาก v0.10.2**

รุ่นนี้แก้ปัญหา **kokoro · tts** ซ่อม/ติดตั้ง Runtime ไม่สำเร็จใน Windows Portable ที่อยู่ในโฟลเดอร์ลึก โดยยังคงโครงสร้าง Universal .vwmodel v2, คิวเสียง และโหมด Live เดิม

## สิ่งที่แก้ไข

- Recipe เดิมอ้างอิง misaki[ja]==0.9.4 และ pyopenjtalk==0.4.1 ซึ่งถูกบังคับคอมไพล์จาก Source ผ่าน CMake/MSBuild บน Windows และพบ FTK1011: could not create the new file tracking log file เมื่อพาธ Build ใน Cache ยาวมาก
- เปลี่ยนเฉพาะ Kokoro Trusted Runtime Recipe เป็น misaki[ja]==0.8.0 + unidic-lite==1.0.8 เพื่อใช้ Japanese G2P ที่ระบบรองรับอยู่แล้วโดยไม่บังคับคอมไพล์ pyopenjtalk
- เพิ่ม Regression Test ป้องกันนำปัญหากลับเข้ามา และปรับเอกสารติดตั้ง

## การทดสอบ

- สร้าง Runtime Kokoro ใหม่บน Windows 10 / Python 3.11 จาก Recipe ใหม่: สำเร็จ ติดตั้ง Dependencies 19 รายการ และ uv pip check ผ่าน
- Portable ที่เคยเกิดปัญหาบนพอร์ต 8775: หลังซ่อมได้สถานะ Runtime ready
- ใช้โมเดล Kokoro v2 สร้าง WAV จริงผ่านทั้งอังกฤษเสียง af_heart และญี่ปุ่นเสียง jf_alpha ที่ 24 kHz
- ทดสอบ Python ในเครื่องพัฒนา 550 tests ผ่าน (skipped 10), UI Smoke Tests ผ่าน และ GitHub Actions สำหรับการแก้ไข Kokoro ก่อนจัด Release ผ่านทั้ง Python 3.11/3.13 และ JavaScript; ผล CI สำหรับ Commit Release ตรวจจาก GitHub Actions
- ยังไม่ยืนยันบน Windows อีกเครื่องที่ไม่มีเครื่องมือพัฒนา หรือความถูกต้องการออกเสียงทุกประโยค

## การติดตั้งและไฟล์แนบ

- **VoxWeaveTTS-v0.10.3-portable.zip** — Windows Portable ที่รวม MakHam Paradee และ Trusted Recipe Kokoro ใหม่ไว้แล้ว
- **Universal .vwmodel v2 ทั้ง 8 แพ็กเกจ** แยกโหลด เช่น Kokoro82M, Vachana, Wayu NC และ M2M100; โมเดลเสริมยังเป็นไฟล์แยก ไม่ได้บันเดิลทั้งหมดใน Portable
- **Verified Wheelhouse 3 ชุด** — Sherpa, PyThaiTTS และ M2M100 สำหรับ Python 3.11 / Windows x64 พร้อม Trusted Lock และ SHA-256
- **TikTok Extension, Source, Docs และ SHA256SUMS** สำหรับตรวจไฟล์ดาวน์โหลด

ก่อนย้ายจากเวอร์ชันเก่า ให้สำรองโฟลเดอร์ Settings, Data, Presets และ Models ของผู้ใช้ก่อนเสมอ แนะนำแตก ZIP ใหม่ลงโฟลเดอร์ใหม่ และคัดลอกเฉพาะข้อมูลที่ต้องการ ไม่คัดลอกไฟล์ src, runtime, scripts หรือ web ของรุ่นเก่าทับรุ่นใหม่

หลังติดตั้งโมเดล Kokoro .vwmodel v2 แล้ว ให้เปิด Engine Providers และเลือกติดตั้ง Runtime Kokoro พร้อมอ่านเงื่อนไขและกดยืนยันการติดตั้งด้วยตนเอง โดยจำเป็นต้องมีอินเทอร์เน็ตสำหรับ Dependencies หากไม่ได้มี Cache ไว้แล้ว

**สิทธิ์:** Wayu Paxa Edge NC ยังเป็น CC BY-NC 4.0 (NonCommercial-only); การติดตั้ง Kokoro/Vachana บนเครื่องผู้ใช้โดยยินยอมไม่ได้เปลี่ยนสิทธิ์การแจก Wheelhouse ของผู้พัฒนาภายนอก Kokoro/Vachana/Wayu runtime wheelhouse ที่ติด HOLD จึงไม่ได้ถูกแนบใน Release นี้

เอกสารเพิ่มเติม: [คู่มือแก้ Kokoro](KOKORO_WINDOWS_RUNTIME_FIX_TH.md), [สิทธิ์ของ Provider](PROVIDER_RIGHTS_READINESS_TH.md), [Release v0.10.2](RELEASE_NOTES_v0.10.2.md)

Release: https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.10.3
