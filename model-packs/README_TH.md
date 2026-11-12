# Model Packages ที่ทดลองแล้ว — VoxWeaveTTS v0.4.2

ไฟล์โมเดลแยกจากตัวโปรแกรมหลัก: **Git Repository เก็บโค้ดสร้างแพ็กเกจ, Manifest, SHA-256, เครดิตและไฟล์ลิขสิทธิ์** ส่วนไฟล์น้ำหนักที่มีขนาดใหญ่จัดเก็บเป็น **GitHub Release Assets** ใน Repository เดียวกัน ไม่ Commit ไฟล์ ONNX ขนาดหลายร้อย MB ลง Git history

**ดาวน์โหลดแพ็กเกจ:** https://github.com/funggier/VoxWeaveTTS/releases/tag/modelpacks-v0.4.2  
**โปรแกรมหลัก:** https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.4.2  
**ข้อมูลเครื่องตรวจสอบได้:** [catalog.json](catalog.json) มี SHA-256 ของไฟล์ `.vwmodel` และไฟล์โมเดลต้นทางที่ Pin ตาม Version

## รุ่นที่แจก

| แพ็กเกจ | เสียง | ประกาศลิขสิทธิ์จากผู้เผยแพร่ | ข้อควรทราบ |
|---|---|---|---|
| Vachana Thai 4 Voices v1.0.0 | 4 เสียง (หญิง 2/ชาย 2) | **MIT** ตาม Hugging Face Model Card ของ VIZINTZOR | ไม่พบรายการข้อมูลฝึกที่แจกแจงครบ ไม่มีการตรวจสิทธิ์เสียงแต่ละคนโดยอิสระ |
| FastThaiG2P Kokoro Thai Som v0.3.0 | Thai Som 1 เสียง | **Apache-2.0** ตาม Repository FastThaiG2P พร้อม `NOTICE`; ชุดข้อมูล Som TTS ระบุ **CC BY 4.0** | ต้องเก็บเครดิตผู้สร้างและชุดข้อมูล ไม่ใช่สิทธิ์ที่ VoxWeaveTTS สร้างเอง |

เราให้ดาวน์โหลดเพื่อทดลองและแจกต่อ **ตามสิทธิ์ที่ผู้เผยแพร่ต้นทางระบุ** โดยมีไฟล์ `legal/license.txt` / `legal/notice.txt` / `legal/attribution.md` อยู่ภายในแพ็กเกจที่เกี่ยวข้อง และมีสำเนาใน Repository:

- [Vachana — MIT และข้อจำกัด](vachana/ATTRIBUTION.md) | [ประกาศ MIT](vachana/LICENSE.txt)
- [FastThaiG2P — Apache/CC BY และข้อจำกัด](fastthaig2p/ATTRIBUTION.md) | [Apache-2.0](fastthaig2p/LICENSE.txt) | [NOTICE ต้นฉบับ](fastthaig2p/NOTICE.txt)

### ข้อเท็จจริงเรื่องสิทธิ์ (สำคัญ)

1. **MIT (Vachana)**: ต้นทางระบุ MIT กับโมเดลบน Hugging Face และเผยแพร่ ONNX สี่เสียงที่ Revision `6fa5f03a26f8ec0c0e0582e9e6812efa84d38688`. ตามเงื่อนไข MIT สามารถคัดลอกและเผยแพร่ต่อได้โดยคงประกาศสิทธิ์และเครดิตของเจ้าของผลงาน แต่ต้นทาง **ไม่ได้แจกแจงสิทธิ์ของข้อมูลฝึกทุกแหล่ง** จึงไม่รับรองสิทธิ์เสียงหรือการใช้งานทุกกรณี
2. **Apache-2.0 (FastThaiG2P)**: Repository ของ Charin Polpanumas / Amazon Web Services แจกโค้ดและโมเดล Thai Som v0.3.0 และมี `LICENSE` กับ `NOTICE` สำหรับการเผยแพร่ต่อ ให้เก็บประกาศเหล่านี้ไว้
3. **CC BY 4.0 (Som TTS)**: ชุดข้อมูลฝึกที่อ้างถึงในงาน FastThaiG2P เผยแพร่โดย Wannaphong Phatthiyaphaibun เป็น CC BY 4.0 ต้องอ้างชื่อผู้สร้าง แหล่งที่มา และลิงก์เงื่อนไข ชุดแพ็กเกจ **ไม่มีไฟล์ชุดข้อมูลฝึก** แต่บันทึกเครดิตไว้
4. **การใช้เชิงพาณิชย์**: ผู้ใช้ไม่ได้ต้องการให้เราออกใบรับรองเชิงพาณิชย์ และเรา **ไม่ได้รับรอง** ความถูกต้องของสิทธิ์เสียงหรือข้อมูลฝึกทุกองค์ประกอบ การไม่รับรองไม่ใช่การเพิ่มเงื่อนไข “ห้ามใช้เชิงพาณิชย์” ให้กับ MIT/Apache/CC BY ที่ต้นทางประกาศ
5. **การแจกต่อ**: ผู้นำไฟล์ไปเผยแพร่ต่อหรือใช้งานในที่อื่นต้องตรวจต้นทางล่าสุด และรักษาเงื่อนไขเดิมทั้งหมดเอง ข้อสงวนสิทธิ์นี้ไม่สามารถยกเว้นภาระตาม License ที่แท้จริงได้

ข้อมูลอ้างอิง: [VachanaTTS](https://huggingface.co/VIZINTZOR/VachanaTTS), [FastThaiG2P v0.3.0](https://github.com/awslabs/FastThaiG2P/releases/tag/v0.3.0), [Som TTS Dataset CC BY 4.0](https://huggingface.co/datasets/pythainlp/som_tts_dataset), [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)

## วิธีติดตั้ง

1. ดาวน์โหลด `VoxWeaveTTS-v0.4.2-portable.zip`, แตกไฟล์ เปิด `VoxWeaveTTS.exe`
2. ดาวน์โหลดเฉพาะ `.vwmodel` ที่ต้องการจากหน้า Model Packages Release ด้านบน
3. ในโปรแกรม เข้าเมนู **ตั้งค่า → จัดการ Model Packages → ติดตั้ง Model Package (.vwmodel)** แล้วเลือกไฟล์ที่ดาวน์โหลด
4. เมื่อรายการแสดง Engine/Model และ Runtime พร้อม ให้เข้า Voice Studio หรือ Live Channel ที่ต้องการ แล้วเลือก Engine และ Voice ของแพ็กเกจนั้น
5. อ่าน License/Attribution ที่รวมไว้ในแพ็กเกจ และตรวจสอบ SHA-256 เทียบกับ `catalog.json` หรือ `SHA256SUMS.txt` ของ Release

**ถ้าเคยติดตั้งแพ็กเกจทดลองเวอร์ชันเดียวกันแล้ว:** ตัวติดตั้งจะไม่ทับไฟล์เดิม ให้นำไฟล์ที่ต้องการเก็บสำรองก่อน เลือกถอนการติดตั้ง *เฉพาะแพ็กเกจและเวอร์ชันนั้น* แล้วติดตั้งแพ็กเกจใหม่ที่มีเอกสารลิขสิทธิ์ครบ

**Runtime**: โปรแกรม v0.4.2 มี Engine Adapter ทั้งคู่ และบันเดิล Python Dependencies บางรายการไว้แล้ว ถ้ารายการใน Model Package Manager แสดง **Runtime ไม่พร้อม** ตรวจ `dependencies` ใน Manifest และคู่มือ [Model Packages](../docs/MODEL_PACKAGES_TH.md) ห้ามคัดลอก DLL/Python Package ที่ไม่ทราบแหล่งที่มาลงเครื่องเพื่อแก้ปัญหาแบบสุ่ม

## สำหรับนักพัฒนา / Rebuild

ดึงโมเดลจาก URL ต้นทางที่ตรึง Revision / Tag แล้ววางตามโฟลเดอร์ของคำสั่งต่อไปนี้ (ต้องเป็นไฟล์ที่มี Hash ตรงกับ `catalog.json`):

```powershell
$env:PYTHONPATH = 'src'
python -m voxweavetts.model_packages pack-vachana
python -m voxweavetts.model_packages pack-fastthai
python scripts/verify_model_pack_release.py --write-catalog
```

คำสั่ง `pack-vachana` และ `pack-fastthai` ใส่เอกสาร License และ Attribution จาก Repository เข้าไปในแพ็กเกจโดยอัตโนมัติ ตัวตรวจสอบจะหยุดเมื่อไฟล์โมเดลเบี่ยงเบนจาก SHA-256 ของผู้เผยแพร่ต้นทาง ไม่ต้องดาวน์โหลดไฟล์ใหม่หรือเรียกโค้ดฝึกโมเดล

> **ไม่มีการเปลี่ยนสัญญาอนุญาตต้นฉบับ** VoxWeaveTTS ทำหน้าที่จัดรูปแบบไฟล์ให้ติดตั้งได้เท่านั้น และให้เครดิตต้นทางตามที่ตรวจสอบพบ ไม่มีการรับประกันการใช้งาน ความเหมาะสม หรือความเป็นเจ้าของเสียง
