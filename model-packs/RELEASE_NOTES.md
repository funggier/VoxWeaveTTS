# Optional Thai Model Packages for VoxWeaveTTS v0.4.2

ไฟล์โมเดลเสียงที่เคยทดสอบแล้ว แจกแยกจาก Windows Portable หลักเพื่อให้ผู้ใช้เลือกดาวน์โหลดเอง **ไม่มีไฟล์ข้อมูลฝึก ไม่มีไฟล์เสียงส่วนตัว และไม่มีโค้ด Python/DLL/EXE ในแพ็กเกจ** ทั้งสองเป็นไฟล์ ZIP นามสกุล .vwmodel ที่ติดตั้งผ่านเมนู **ตั้งค่า → จัดการ Model Packages**

## แพ็กเกจดาวน์โหลด / Assets

| File | Voices | Archive SHA-256 | Source-declared license |
|---|---|---|---|
| VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel | 4 (หญิง 2 / ชาย 2) | c782818d6bc99f7da1e3540d308cedde20f41dc204d2b34ee002089a8057f5f3 | MIT (VIZINTZOR Model Card) |
| VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel | 1 (Thai Som) | 6aff293704ec5e9f25941eafb897b434c3be47f75eecd89aadc9cb6df9cc6016 | Apache-2.0 (FastThaiG2P); Som TTS training dataset CC BY 4.0 |

SHA-256 ของทุกไฟล์โมเดลภายในแพ็กเกจตรงกับผู้เผยแพร่ต้นทางที่ Pin Revision/Tag แล้ว มี Manifest ที่ตรวจ SHA-256 รายไฟล์ และมี SHA256SUMS.txt ให้ดาวน์โหลดตรวจสอบไฟล์แพ็กเกจ

## ลิขสิทธิ์แยกตามความจริง / License scope

**Vachana Thai Four Voices:** [VIZINTZOR](https://huggingface.co/VIZINTZOR/VachanaTTS) ระบุ MIT ใน Model Card ของน้ำหนักโมเดลที่ Revision 6fa5f03a26f8ec0c0e0582e9e6812efa84d38688. การแจกต่ออาศัยประกาศ MIT ของผู้เผยแพร่ พร้อมเก็บไฟล์ legal/license.txt และ legal/attribution.md. รายละเอียดสิทธิ์ชุดข้อมูลฝึกและผู้พูดทุกคนยังไม่ได้ตรวจสอบครบโดยอิสระ

**FastThaiG2P Kokoro Thai Som:** [FastThaiG2P release v0.3.0](https://github.com/awslabs/FastThaiG2P/releases/tag/v0.3.0) อยู่ใน Repository ที่ระบุ Apache-2.0 พร้อม LICENSE และ NOTICE ต้นฉบับ ซึ่งแนบใน legal/license.txt / legal/notice.txt. งานต้นทางระบุ [Som TTS Dataset](https://huggingface.co/datasets/pythainlp/som_tts_dataset) เป็น CC BY 4.0 เผยแพร่โดย Wannaphong Phatthiyaphaibun; จัดเครดิตและลิงก์เงื่อนไขอยู่ใน legal/attribution.md

**review_required** ใน Manifest หมายถึง VoxWeaveTTS ยังไม่ได้รับรองสิทธิ์ของข้อมูลฝึก/บุคลิกเสียงทุกองค์ประกอบ ไม่ได้เปลี่ยน MIT/Apache/CC BY ให้เป็นข้อห้ามเชิงพาณิชย์ เราเผยแพร่ต่อโดยอาศัยสิทธิ์จากผู้เผยแพร่ต้นทาง ไม่ได้ออกหนังสือรับรองการใช้งานเชิงพาณิชย์หรือสิทธิ์ในเสียงทุกกรณี ผู้ใช้และผู้แจกต่อรายถัดไปต้องตรวจ License/Notice และปฏิบัติตามเงื่อนไขทั้งหมดด้วยตนเอง ข้อสงวนความรับผิดไม่ใช่สิทธิ์แจกจ่ายที่เหนือกว่า License ต้นฉบับ

## ติดตั้ง / Install

1. เปิด [VoxWeaveTTS Portable v0.4.2](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.4.2) บน Windows
2. ดาวน์โหลดไฟล์ .vwmodel ที่ต้องการจากส่วน Assets ของ Release นี้
3. เปิด **ตั้งค่า → จัดการ Model Packages → ติดตั้ง Model Package (.vwmodel)**
4. เลือก Engine ของแพ็กเกจใน Studio/Live ที่ต้องการ แล้วเลือกเสียง
5. หากเคยติดตั้งแพ็กเกจ ID/Version เดียวกัน ให้สำรองข้อมูลก่อน แล้วถอนแพ็กเกจเฉพาะชุดนั้นก่อนลงใหม่ ระบบไม่เขียนทับเวอร์ชันที่มีอยู่

**ทดสอบกับ v0.4.2 Portable จริงแล้ว:** Vachana th_f_1 สังเคราะห์ WAV 22,050 Hz สำเร็จ และ FastThaiG2P thai_som สังเคราะห์ WAV 24,000 Hz สำเร็จ หลังติดตั้งผ่าน Runtime ของ Portable รุ่นที่เผยแพร่แล้ว

**ข้อมูลเพิ่มเติม:** [คู่มือ Model Packages และลิขสิทธิ์](https://github.com/funggier/VoxWeaveTTS/blob/modelpacks-v0.4.2/model-packs/README_TH.md) · [Manifest และ SHA-256](https://github.com/funggier/VoxWeaveTTS/blob/modelpacks-v0.4.2/model-packs/catalog.json)

These independently repacked optional model files do not imply ownership by VoxWeaveTTS. Preserve all upstream notices and check original conditions before further redistribution.
