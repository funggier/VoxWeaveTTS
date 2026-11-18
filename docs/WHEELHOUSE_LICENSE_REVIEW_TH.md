# Wheelhouse Phase C — รายงานคัดกรองสิทธิ์ Dependencies

**สถานะ:** ตรวจเบื้องต้นในเครื่องพัฒนา วันที่ 17 พฤศจิกายน 2026; **ไม่ใช่การอนุมัติให้แจกจ่ายหรือคำรับรองการใช้งานเชิงพาณิชย์**

**อัปเดต 18 พฤศจิกายน 2026:** เพิ่ม First-party Rights Gate สำหรับ Wayu NC / Vachana / Kokoro ซึ่งปฏิเสธการย้าย Candidate ไป Trusted Lock แม้จะระบุ `--publish-reviewed` จนกว่าจะตรวจหลักฐานสิทธิ์และแก้ Policy ใน Source โดยเจตนา พร้อมสถานะสิทธิ์ใน Runtime Registry/Portable Doctor [รายละเอียด](PROVIDER_RIGHTS_READINESS_TH.md)

ระบบ Wheelhouse ต้องตรวจ **สองเรื่องที่เป็นอิสระกัน**:

1. **ความสมบูรณ์ทางเทคนิค:** เวอร์ชัน, Python/OS ABI, Dependency closure, Trusted Recipe, ZIP และ SHA-256 ของไฟล์ Wheel
2. **สิทธิ์การใช้/แจกจ่าย:** License ของโค้ดและไฟล์ประกอบ (รวมข้อมูลคำศัพท์, เสียง, ไลบรารี native และ NOTICE), Provenance, เงื่อนไข Attribution/Copyleft/NonCommercial, สิทธิ์ในโมเดลและข้อมูลฝึก

Hash ผ่าน **ไม่ได้แปลว่า** มีสิทธิ์แจกจ่ายไฟล์ หรือได้รับอนุญาตให้ใช้โมเดลเชิงพาณิชย์

## ผลตรวจปัจจุบัน

| Runtime | Wheel (รวม Dependencies) | ขนาดไฟล์รวม | ทดสอบติดตั้ง Offline ในโฟลเดอร์ทดลอง | Trusted Lock ใน Source | ประเด็นสิทธิ์ที่ต้องตรวจ |
|---|---:|---:|---|---|---|
| Sherpa | 3 | 31,744,498 B | ผ่าน | มี | ประกาศสิทธิ์ของ ONNX/native library และการแจกแพ็กเกจ |
| PyThaiTTS | 26 | 72,442,984 B | ผ่าน | มี | NOTICE/ไฟล์ third-party ใน NumPy; FlatBuffers ไม่ได้แนบ License ใน Wheel |
| M2M100 | 25 | 284,707,898 B | ผ่าน (เฉพาะ Runtime ไม่ได้แปลจริง) | มี | SentencePiece/Tokenizers บาง Wheel ไม่ฝัง License/Metadata ครบ; ตรวจต้นทางและ NOTICE เพิ่ม |
| Vachana | 14 | 58,375,295 B | ผ่านแบบ Draft ทดลอง | **ยังไม่เผยแพร่** | `vachanatts 0.0.7` Wheel ไม่ประกาศ License และไม่มี LICENSE; ต้องยืนยันสิทธิ์โค้ด/น้ำหนักโมเดลแยก |
| Kokoro | 31 | 92,429,433 B | ผ่านแบบ Draft ทดลอง | **ยังไม่เผยแพร่** | `phonemizer` ระบุ GPLv3-or-later; `espeakng-loader` ไม่มี License ใน Wheel; ต้องตรวจการแจกจ่ายและ Copyleft รวมถึง UniDic/OpenJTalk |

`vachanatts` Package บน PyPI/GitHub ไม่แสดง License ชัดใน Wheel ที่รวบรวม จึง **ไม่ตีความว่าไฟล์สาธารณะ = ใช้งาน/แจกจ่ายได้อิสระ** แม้น้ำหนัก VachanaTTS บางส่วนมี Model Card ระบุ MIT ก็ตาม เพราะสิทธิ์โค้ด Runtime และสิทธิ์น้ำหนักโมเดลเป็นคนละประเด็น

`phonemizer` GPLv3-or-later ไม่ได้ห้ามการใช้เชิงพาณิชย์โดยตัวมันเอง แต่การแจกจ่ายอาจมีภาระข้อกำหนดของ License/Copyleft ต้องตรวจตามรูปแบบการรวมและการเผยแพร่ซอฟต์แวร์จริง

ใน NumPy มีคำประกาศหลาย License ขององค์ประกอบที่ Bundled รวมถึง GCC runtime exception ตัวตรวจอัตโนมัติจะเตือน `bundled-third-party-review` ไม่สรุปว่า NumPy ทั้งตัวเป็น GPL

## สร้างรายงานเพื่อทบทวน

```powershell
.\.venv\Scripts\python.exe scripts\audit_wheelhouse_rights.py --runtime-id pythaitts --source cache\temp\phasec-pythaitts-candidate
.\.venv\Scripts\python.exe scripts\audit_wheelhouse_rights.py --runtime-id m2m100 --source cache\temp\phasec-m2m100-candidate
.\.venv\Scripts\python.exe scripts\audit_wheelhouse_rights.py --runtime-id vachana --source cache\temp\phasec-vachana-candidate
.\.venv\Scripts\python.exe scripts\audit_wheelhouse_rights.py --runtime-id kokoro --source cache\temp\phasec-kokoro-candidate
```

ผลรายแพ็กเกจเก็บใน `cache/wheelhouse-rights/<id>.json` (ไม่รวม Git/Release) โดย `legal_clearance=false` เสมอ และแสดงสถานะ `manual-review-required`. ตัวตรวจไม่ตัดสินว่าชุดใดสามารถใช้เชิงพาณิชย์ได้ตามกฎหมายด้วยตนเอง

## ขอบเขตการทดสอบ

มีการติดตั้งแบบ **Offline จริงในโฟลเดอร์แยก** สำหรับทั้ง 5 Runtime ที่ระบุข้างต้น โดยใช้ Verified Wheel/Lock ใน Sandbox; ชุด Draft ที่มีข้อกำหนดสิทธิ์ต้องทบทวนถูกวาง Lock เฉพาะใน Sandbox เพื่อทดสอบ ไม่ได้เพิ่มเป็น Trusted Lock ของแอปหลัก

ทดสอบการย้ายโฟลเดอร์จำลองด้วย Sherpa: ติดตั้ง → เปลี่ยนพาธ → ตรวจพบ `relocated` → สร้าง Runtime ใหม่แบบ Offline จาก Wheelhouse → ได้ `ready` พร้อม Cleanup ถูกต้อง ทั้งหมดทำในพื้นที่ชั่วคราวของไดรฟ์ T: **ยังไม่เท่ากับการทดสอบย้ายข้ามเครื่องจริง** ที่อาจมี Python Base/DLL หรือ OS ต่างกัน

ยัง **ไม่ได้** จัดทำแพ็กเกจ Runtime ของ Wayu NC (ใช้ Recipe Git/URL และน้ำหนักโมเดลสิทธิ์ NC) และ **ยังไม่ได้** ตรวจการแปลจริงของ M2M100 เพราะข้อจำกัด Commit/Paging File เดิม

## ก่อนแจกจ่าย

ต้องจัดเก็บ Notices/License ของไลบรารีทุกตัว, ตรวจใบอนุญาตโมเดล/ชุดข้อมูล, จัด Source/Attribution สำหรับ Copyleft ตามเงื่อนไข และยืนยันสิทธิ์ของ `vachanatts`/Kokoro dependencies ที่ไม่ชัดเจน แล้วจึงค่อยจัดทำ Wheelhouse ZIP แยกตาม Python ABI/Windows Platform และทดสอบบนเครื่องปลายทางก่อน Release
