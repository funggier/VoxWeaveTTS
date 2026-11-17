# VoxWeaveTTS v0.9.5 — Portable, Managed Runtimes & Removable MakHam

**Release:** 17 พฤศจิกายน 2026 · Windows 10/11 x64 · ต่อจาก [v0.9.4](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.9.4)

## มีอะไรใหม่

- **Runtime Environment Registry:** จัดการ Runtime ของ TTS/AI พร้อมจำนวนโมเดลที่ใช้งานร่วมกัน ถอน Runtime ได้เฉพาะเมื่อไม่มีโมเดลใดอ้างอิง โดยต้องยืนยันผ่าน UI และมีการตรวจ Origin/Intent/Fingerprint อีกครั้งใน API
- **MakHam เป็นโมเดลที่ถอนติดตั้งได้:** แพ็กเกจที่ติดตั้งมาใน Portable อยู่ที่ `models/packages/makham-paradee/1.0.0/`, มี Archive กู้คืนและไฟล์ `VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0.vwmodel` แบบแยก; Engine ID `makham-paradee-cpu`, Preset และ Language Routes เดิมยังใช้ได้
- **Legacy MakHam:** ถอนได้เฉพาะไฟล์น้ำหนักเดิมที่ตรวจ SHA-256 ถูกต้อง และสำรองแพ็กเกจกู้คืนก่อน ไม่ลบข้อมูลผู้ใช้หรือ Shared Runtime
- **ติดตั้งจากไฟล์ .vwmodel กลาง:** จำแนก TTS หรือ AI/Translation ตาม Manifest โดยอัตโนมัติ ไม่ส่ง M2M100 ไปติดตั้งแบบ TTS อีก
- **M2M100 Runtime:** เพิ่มระบบติดตั้ง/ซ่อม PyTorch + Transformers แบบแยก Environment ใน `runtime/ai-envs/m2m100/` ด้วยสูตร Trusted Dependencies และ uv. Worker แปลผ่าน JSON IPC แบบ Offline และใช้โมเดลที่โหลดแล้วซ้ำได้
- **Memory diagnostics:** แจ้ง RAM/Commit/Pagefile ไม่พอ (WinError 1455) โดยไม่ปิด Ollama หรือแก้ Pagefile เอง
- **Reproducible .vwmodel:** บันทึก ZIP Metadata แบบคงที่เพื่อสร้าง Hash ซ้ำได้จาก Asset ที่เหมือนเดิม
- อ่าน [Model Package v2](MODEL_PACKAGE_V2_ARCHITECTURE_TH.md) เพื่อแยกส่วนที่ใช้งานจริงและแผนต่อไป

## การติดตั้ง

1. แตก `VoxWeaveTTS-v0.9.5-portable.zip` ลงโฟลเดอร์ที่ต้องการ แล้วเปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd`
2. MakHam เป็น Default Model ที่ติดตั้งอยู่แล้ว ไม่จำเป็นต้องติดตั้งซ้ำ สามารถถอนน้ำหนักผ่าน Model Package Manager โดย Engine/Adapter ยังอยู่
3. ดาวน์โหลดโมเดลเสริมเป็นไฟล์ .vwmodel แล้วติดตั้งใน Model Package Manager; ตรวจ Runtime Environment Registry ก่อนลบ Runtime
4. M2M100: ตั้งค่า → AI / Translation → ติดตั้ง Model Package → ติดตั้ง/ซ่อม Runtime M2M100 → เลือกโมเดลและคู่ภาษา; อ่าน [คู่มือ M2M100](M2M100_SETUP_TH.md)
5. สำรอง `data/`, `presets/`, `voices/` และไฟล์แพ็กเกจส่วนตัวก่อนอัปเกรด

## Assets ที่รวมใน GitHub Release

1. `VoxWeaveTTS-v0.9.5-portable.zip`
2. `VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0.vwmodel`
3. `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel`
4. `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel`
5. `VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel`
6. `VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel`
7. `VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel`
8. `VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0.vwmodel` — **NonCommercial**
9. `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` — Experimental Translation
10. `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip`
11. `VoxWeaveTTS-v0.9.5-source.zip` — Tagged source snapshot
12. `VoxWeaveTTS-v0.9.5-docs.zip` — Tagged documentation
13. `SHA256SUMS-v0.9.5.txt` — checksums for the other 12 assets

## License และข้อจำกัด

- **Wayu Paxa Edge:** CC BY-NC 4.0 — แจก/ดัดแปลงได้เฉพาะ NonCommercial โดยให้ Attribution, License link, Modification notice และปฏิบัติตาม Acceptable Use; **แยกออกจาก Portable ZIP**
- **MakHam:** โมเดล Apache-2.0, ข้อมูลชุดฝึกที่อ้างอิงเป็น CC BY 4.0. รวม License/Attribution แต่ยังไม่รับรองสิทธิ์เสียงและข้อมูลต้นทางทุกกรณีสำหรับการใช้งานเชิงพาณิชย์
- **Supertonic 3:** OpenRAIL-M ไม่ใช่ MIT ทั้งโมเดล; FastThaiG2P, Vachana, Kokoro และ Melo ต้องอ่านสิทธิ์และ Attribution ของแต่ละแพ็กเกจ
- **M2M100:** การแปลไทยยัง Experimental, น้ำหนักโมเดลกับ Runtime เป็นคนละส่วน และต้องมี RAM/Pagefile มากพอ; อาจต้องซ่อม Python venv หลังย้ายโฟลเดอร์
- **Universal Model Package v2 ยังไม่เสร็จทั้งหมด:** Runtime Registry / Reference-safe Uninstall / MakHam Managed Package ทำงานได้แล้ว แต่ Manifest v2 + Bundled Offline Wheelhouse และการแชร์ Runtime ข้าม Provider โดยอัตโนมัติยังไม่เปิดใช้

ตรวจ SHA-256 กับ `SHA256SUMS-v0.9.5.txt`, อ่าน `THIRD_PARTY_NOTICES.txt` และ `legal/` ในแต่ละโมเดล
