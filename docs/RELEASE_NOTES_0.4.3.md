# VoxWeaveTTS v0.4.3 — Windows Portable + Optional Model Packages

**รุ่นแก้ไขการเชื่อมต่อ Live/Discord และรวม Model Packages ที่ทดลองแล้วใน Release เดียวกัน**

## ไฟล์ดาวน์โหลดใน Release นี้

| Asset | รายละเอียด |
|---|---|
| `VoxWeaveTTS-v0.4.3-portable.zip` | โปรแกรม Windows 10/11 x64 แบบ Portable บันเดิล **MakHam Paradee (CPU ONNX)** เท่านั้น |
| `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel` | แพ็กเกจเสียง Vachana ภาษาไทย 4 เสียง (หญิง 2/ชาย 2) |
| `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` | แพ็กเกจเสียง FastThaiG2P/Kokoro Thai Som 1 เสียง |
| `SHA256SUMS.txt` | SHA-256 สำหรับตรวจสอบไฟล์ดาวน์โหลดทั้ง 3 รายการ |

**หมายเหตุ:** Model Packages เป็นไฟล์เสริมแยกจาก Portable ZIP เพื่อไม่ให้โปรแกรมหลักมีขนาดใหญ่ ผู้ใช้เลือกดาวน์โหลดเฉพาะโมเดลที่ต้องการได้

## แก้ไขใน v0.4.3

- เมื่อกด **เชื่อมต่อ** ใน YouTube LIVE / Discord Bot / Discord Client โปรแกรมขอ **owner token ของโหมดใหม่** เพื่อแก้ปัญหา `source monitor requires the active mode owner token` ที่เกิดหลัง Backend รีสตาร์ตหรือถูกแท็บอื่นขอสิทธิ์ไปก่อน
- การขอสิทธิ์ใหม่กระทบเฉพาะช่องทางนั้น ไม่ตัดการอ่านของช่องทางอื่นที่กำลังทำงานอยู่
- แยกข้อความข้อผิดพลาด **HTTP 400/401/403/404** ของ YouTube/Discord ให้ช่วยวิเคราะห์ประเภทปัญหา เช่น ข้อมูลไม่ถูกต้อง, Credentials, สิทธิ์ API/Quota, ไม่พบ Live Chat/Channel โดยไม่แสดง API Key/Token ลงใน Error
- เมื่อเกิดข้อผิดพลาดที่ไม่คาดคิดใน Worker รับข้อความ จะรายงานสถานะและ Retry แทนการหยุดทำงานแบบไม่มีข้อมูล
- รักษาความสามารถของ v0.4.2: รับหลายช่องทางพร้อมกัน, เล่นเสียงแบบ serial/overlap, ปรับ Engine/Voice/Speed/DSP แยกแต่ละโหมด, อ่านชื่อผู้ส่งได้/ไม่อ่านได้ตามโหมด, Preset แบบ JSON และติดตั้ง Model Packages ได้

**ข้อจำกัดการแก้ไข:** การทำ Owner Token ใหม่ไม่ได้แก้ API Key ที่ไม่ถูกต้อง, ข้อจำกัด Quota หรือสิทธิ์ของบัญชี YouTube/Discord เอง ต้องตรวจข้อความสถานะ API ที่แสดงและเงื่อนไขผู้ให้บริการด้วย

## โมเดลที่แนบและสิทธิ์ต้นทาง

| โมเดล | สิทธิ์ที่ผู้เผยแพร่ต้นทางประกาศ | เครดิต/เงื่อนไขที่ควรอ่าน |
|---|---|---|
| MakHam Paradee (ใน ZIP หลัก) | Apache-2.0 จาก Model Metadata ของ PyThaiNLP | เครดิตตาม THIRD_PARTY_NOTICES.txt |
| Vachana Thai 4 Voices (.vwmodel) | **MIT** จาก Model Card ของ VIZINTZOR | เก็บ MIT License/Attribution; ยังไม่มีการตรวจข้อมูลฝึกและสิทธิ์เสียงครบโดยอิสระ |
| FastThaiG2P/Kokoro Thai Som (.vwmodel) | **Apache-2.0** จาก Repository FastThaiG2P และ **CC BY 4.0** สำหรับ Som TTS Dataset ที่เกี่ยวข้อง | เก็บ LICENSE, NOTICE และเครดิตชุดข้อมูลฝึก/ผู้สร้าง |

Model Packages มีไฟล์ `legal/license.txt`, `legal/attribution.md` และ `legal/notice.txt` (สำหรับ FastThaiG2P) รวมอยู่ในแต่ละแพ็กเกจ มี Source/Version และ SHA-256 ของไฟล์น้ำหนักจริงใน Manifest

**การแจกต่อ:** แจกตามสิทธิ์ที่ผู้เผยแพร่ต้นทางระบุ ไม่ใช่การรับรองว่ามีสิทธิ์ในข้อมูลฝึกและเสียงทุกชิ้นโดยสมบูรณ์หรือรับรองเชิงพาณิชย์ ผู้ใช้และผู้แจกต่อรายถัดไปต้องตรวจต้นทางและรักษาเงื่อนไข License/Attribution ด้วยตนเอง ข้อความปฏิเสธความรับผิดชอบไม่ใช่การอนุญาตแทนเจ้าของสิทธิ์

อ้างอิง: [Vachana Model Card](https://huggingface.co/VIZINTZOR/VachanaTTS) · [FastThaiG2P v0.3.0](https://github.com/awslabs/FastThaiG2P/releases/tag/v0.3.0) · [Som TTS Dataset](https://huggingface.co/datasets/pythainlp/som_tts_dataset) · [รายการสิทธิ์แยกตามแพ็กเกจ](https://github.com/funggier/VoxWeaveTTS/blob/v0.4.3/model-packs/README_TH.md)

## ติดตั้ง

1. ดาวน์โหลดและแตก `VoxWeaveTTS-v0.4.3-portable.zip` ลงในโฟลเดอร์ที่เขียนไฟล์ได้ เช่น `T:\Apps\VoxWeaveTTS`
2. เปิด `VoxWeaveTTS.exe` (หรือ `Start-Console.cmd` หากไม่สามารถเปิด Launcher ได้) แล้วเข้า `http://127.0.0.1:8765/`
3. ทดลอง MakHam ที่ติดมากับโปรแกรมก่อน
4. หากต้องการใช้โมเดลเพิ่ม ดาวน์โหลดไฟล์ `.vwmodel` จาก Assets ใน Release นี้ เข้าเมนู **ตั้งค่า → จัดการ Model Packages → ติดตั้ง Model Package (.vwmodel)** แล้วเลือกไฟล์
5. กลับไปแต่ละโหมดแล้วเลือก Engine/Voice ที่ติดตั้ง (ถ้าลงแพ็กเกจ ID และ Version เดียวกันแล้ว ต้องสำรอง/ถอนของเดิมก่อนลงใหม่)
6. กรอก API Key / Channel ID / ข้อมูลบัญชีที่ได้รับอนุญาตเอง แล้วกด **เชื่อมต่อ** อีกครั้ง

**อัปเกรดจากเดิม:** สำรอง `data/`, `presets/` และ `models/packages/` ก่อน ไม่ให้การแตก ZIP ใหม่เขียนทับข้อมูลของผู้ใช้ โปรแกรมไม่บันเดิล Credentials ส่วนตัวลงใน Release

## ผลตรวจสอบ

- Python unit tests: **190 ผ่าน**
- JavaScript browser/queue tests: **17 ชุดผ่าน**
- Mock regression: owner token ใหม่เมื่อ Connect, ไม่กระทบช่องทางอื่น, HTTP error แบบไม่เปิดเผย Secrets
- Optional Vachana และ FastThaiG2P ถูกตรวจ SHA-256 ตรงกับไฟล์ต้นทางที่ตรึง Revision/Tag; ติดตั้งและสร้าง WAV ภาษาไทยกับ Runtime ของ v0.4.2 Portable สำเร็จ (การทดสอบ v0.4.3 แยกตามขั้นตอน Release)
- **ยังไม่ได้ยืนยันว่าบัญชี YouTube/Discord ทุกบัญชีเชื่อมต่อสำเร็จจริง** โดยเฉพาะกรณี API Key, Quota หรือสิทธิ์เข้าถึงช่องที่แตกต่างกัน

Source: https://github.com/funggier/VoxWeaveTTS

See also: [Portable Guide](https://github.com/funggier/VoxWeaveTTS/blob/v0.4.3/docs/PORTABLE.md) · [Model Packages Guide](https://github.com/funggier/VoxWeaveTTS/blob/v0.4.3/docs/MODEL_PACKAGES_TH.md)
