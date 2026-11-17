# VoxWeaveTTS v0.9.4 — Wayu Paxa Edge NC Model Package

**Release:** 17 พฤศจิกายน 2026 · **Windows 10/11 x64 Portable** · ส่วนเพิ่มจาก [v0.9.3](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.9.3)

รุ่นนี้เพิ่มเติมแพ็กเกจโมเดล **Wayu Paxa Edge [NC / NonCommercial]** ที่ติดตั้งผ่าน **Model Package Manager** ได้จริง โดยนำโมเดลต้นฉบับภาษาไทย/อังกฤษและทั้ง 12 เสียงมาจัดเป็นไฟล์ `.vwmodel` **แยกจาก Portable** เพื่อแสดง License อย่างชัดเจน ผู้ใช้ที่ต้องการใช้งานเชิงพาณิชย์ **ห้ามใช้** โมเดลนี้

## สิ่งที่เพิ่ม

- รองรับ `wayu-nc-v1` ในรูปแบบ `.vwmodel` ของโปรแกรม โดยไม่ต้องนำไฟล์ไปวางใน `models/personal/` ด้วยตนเอง
- แพ็กเกจชื่อ `VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0.vwmodel` แสดงป้าย **[NC / NonCommercial]** และ `commercial_status=hold` ในหน้าเลือกโมเดล
- รองรับ **ภาษาไทย (th) / อังกฤษ (en)** สำหรับเสียงทั้ง 12 Voice และกำหนด Route ตามภาษาได้เหมือนโมเดลอื่น
- แพ็กเกจใหม่มี Engine ID `model-wayu-paxa-edge-nc-1_0_0` แยกจาก `personal-nc-wayu-paxa-edge-cpu` เดิม จึงไม่เขียนทับ Preset/Route ที่มีอยู่
- Engine Worker ของ Wayu ใช้ Runtime อิสระ `runtime/engine-envs/wayu-nc` และแยกเสียงตาม Engine ID เมื่ออ่านคนละโมเดล
- เพิ่มการป้องกันไฟล์ PyTorch แบบ serialized: Installer ยอมรับเฉพาะน้ำหนักโมเดล **ต้นฉบับที่มี SHA-256 ตรงกับ Revision ที่ตรวจสอบ** ทั้ง `model.pth` และ `voices/*.pt`; Worker ตรวจซ้ำก่อนโหลดและปฏิเสธแพ็กเกจที่ถูกแก้ไขหรือถูกสลับไฟล์
- ไฟล์แพ็กเกจเก็บ `README.md` ต้นฉบับ, `legal/license.txt`, `legal/attribution.md` และ `legal/acceptable-use.txt` พร้อมลิงก์สิทธิ์และข้อจำกัด
- รวมฟีเจอร์ทั้งหมดของ v0.9.3 เช่น เลือกอ่านอังกฤษได้กับทุกโมเดล TTS, Worker Gateway, Mixed-language WAV, Live Chat Mode, Translation, STOP Process และการจัดการ Model Packages

## สิทธิ์และข้อจำกัด Wayu NC

| รายการ | ข้อเท็จจริง |
|---|---|
| โมเดล | Wayu-Paxa-TTS-Edge (Wayu Research / wayu-ai) |
| แหล่งที่มา | https://huggingface.co/wayu-ai/wayu-paxa-tts-edge |
| Revision | `8196688df56a8d08ccfa186505343adff412ab6b` |
| License ของน้ำหนักและเสียง | **CC BY-NC 4.0 International** — https://creativecommons.org/licenses/by-nc/4.0/ |
| สิทธิ์การแชร์/ดัดแปลง | **อนุญาตเฉพาะ NonCommercial** ตาม CC BY-NC 4.0 โดยต้องระบุผู้สร้าง, อ้างอิง License, แจ้งการแก้ไข และไม่เพิ่มข้อจำกัดที่ขัด License |
| เงื่อนไขเพิ่มเติม | Wayu Research Acceptable Use — https://www.wayuresearch.org/terms#acceptable-use |
| การเปลี่ยนแปลง | น้ำหนักโมเดล, Voice Assets และ Config **ไม่ถูกปรับแก้**; เพิ่มเฉพาะ ZIP/.vwmodel manifest และไฟล์ Legal/Attribution |
| ผู้สร้างและงานวิจัย | Kunat Pipatanakul, Potsawee Manakul, Warit Sirichotedumrong, Sittipong Sripaisarnmongkol, Pakorn Nathong และ Phatrasek Jirabovonvisut; https://arxiv.org/abs/2609.03502 |
| หมายเหตุ | ไม่รับรองสิทธิ์เชิงพาณิชย์ ไม่ใช่ผลิตภัณฑ์ที่ Wayu Research สนับสนุนหรือรับรอง ไม่มีการรับประกันคุณภาพหรือการใช้งาน |

**สำคัญ:** สิทธิ์โมเดล CC BY-NC 4.0 ใช้กับแพ็กเกจ Wayu แยกนี้ **ไม่ใช่** สิทธิ์ MIT ของโปรแกรม VoxWeaveTTS และไม่ได้เปลี่ยนสิทธิ์ของโมเดลอื่น น้ำหนัก Wayu NC **ไม่มีอยู่ใน Portable ZIP หลักหรือ Git Source** แต่ให้ดาวน์โหลดเป็น Asset NC แยกในหน้า Release ตามการอนุญาตให้แชร์แบบไม่เชิงพาณิชย์

## ดาวน์โหลดครบ 10 Assets

1. `VoxWeaveTTS-v0.9.4-portable.zip` — โปรแกรม Portable พร้อม Python 3.11, MakHam, UI และการรองรับ Package Wayu NC (ไม่รวม NC Weights)
2. `VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0.vwmodel` — **Wayu NC โมเดลไทย/อังกฤษ 12 เสียง** (Asset ใหม่)
3. `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel`
4. `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel`
5. `VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel`
6. `VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel`
7. `VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel`
8. `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` — ทดลองแปลภาษา
9. `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip`
10. `SHA256SUMS-v0.9.4.txt` — SHA-256 ของไฟล์ทั้ง 9 รายการข้างต้น

รายการเสริมที่ไม่เกี่ยวข้องกับ Wayu คงน้ำหนักไฟล์และ SHA-256 เดิมจาก v0.9.3 ไม่มีการฝึกหรือเปลี่ยนโมเดลโดยไม่จำเป็น

## วิธีติดตั้ง Wayu NC

1. แตก `VoxWeaveTTS-v0.9.4-portable.zip` ลงโฟลเดอร์ใหม่ที่เขียนได้บนไดรฟ์ใดก็ได้ จากนั้นเปิด `VoxWeaveTTS.exe` หรือ `Start-Console.cmd`
2. ดาวน์โหลดไฟล์ `...Wayu...NC...vwmodel` แยก และเปิด **ตั้งค่า → Model Packages → ติดตั้งจากไฟล์** เพื่อเลือกไฟล์ดังกล่าว; โปรแกรมตรวจโครงสร้าง Manifest และ SHA-256 ก่อนรับ
3. เลือก **Wayu / Install / Repair Runtime** ถ้า Runtime ยังไม่พร้อม (ต้องมี `uv` และอินเทอร์เน็ตสำหรับดาวน์โหลด Dependencies ครั้งแรก) โมเดลจะไม่ถูกดาวน์โหลดซ้ำ เพราะอยู่ใน `.vwmodel` แล้ว
4. เมื่อ Runtime พร้อม เลือก Engine **[NC / NonCommercial] Wayu Paxa Edge ... v1.0.0** กับภาษาไทยหรืออังกฤษ และเลือก Voice ที่ต้องการ
5. อย่าใช้โมเดลนี้ในการผลิตสื่อหรือบริการเชิงพาณิชย์; ยึดตาม CC BY-NC 4.0 และ Wayu Research Acceptable Use

สำหรับ Source Developer สามารถสร้างแพ็กเกจเองจากไฟล์น้ำหนักที่ดาวน์โหลดไว้ในเครื่องด้วย `python -m voxweavetts.model_packages pack-wayu` โดยระบุ `--source` และ `--output` ได้; น้ำหนักต้องตรงกับ Revision เดิมเพื่อป้องกันไฟล์ดัดแปลงที่อาจเป็นอันตราย

## การทดสอบ

- ตรวจ Model Manifest, License, 12 Voices, การติดตั้งแบบ Atomic และ SHA-256 ทั้งฝั่ง Installer/Worker
- สร้างเสียงจริงผ่าน Engine ID ของแพ็กเกจใหม่ทั้งภาษาไทยและอังกฤษ และยืนยันว่า Engine Personal เดิมยังใช้ได้
- Python Unit Tests, JavaScript UI Smokes, Portable self-contained Python, ZIP CRC และการแตกแพ็กเกจไปโฟลเดอร์อื่น
- ตรวจขนาดไฟล์และ Digest SHA-256 ของ Assets ที่อัปโหลดจริงบน GitHub ก่อนเผยแพร่

เอกสาร: [โมเดล NC ส่วนตัวและแบบแพ็กเกจ](PERSONAL_NONCOMMERCIAL_VOICES_TH.md) · [ภาษาที่โมเดลรองรับ](MODEL_LANGUAGE_CAPABILITIES_TH.md) · [นโยบายสิทธิ์การใช้งาน](COMMERCIAL_LICENSE_POLICY_TH.md) · [Worker Gateway](ENGINE_WORKER_GATEWAY_TH.md)
