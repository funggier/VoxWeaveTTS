# Wayu Paxa Edge NC — Native Universal .vwmodel v2

**Release:** นำเสนอโมเดลตั้งแต่ v0.10.1; การยินยอมก่อนติดตั้ง Runtime เพิ่มใน v0.10.2 · Windows 10/11 x64 · Python 3.11 · Thai / English · 12 voices

**สิทธิ์: [NC / NonCommercial] — CC BY-NC 4.0 เท่านั้น** ไม่อนุญาตให้ใช้น้ำหนักโมเดลหรือเสียงที่ได้ในลักษณะเชิงพาณิชย์ตามเงื่อนไขของเจ้าของผลงาน ห้ามตีความ MIT License ของโค้ด VoxWeaveTTS ว่าอนุญาตให้ใช้โมเดลนี้เชิงพาณิชย์

## สิ่งที่เพิ่ม

แพ็กเกจใหม่ชื่อ `VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0-format-v2.vwmodel` ใช้ **Native .vwmodel v2** เต็มรูปแบบ ไม่ต้องอาศัย v1 manifest และไม่ได้ติดตั้ง Dependencies จาก Archive

- **Engine ID:** `model-wayu-paxa-edge-nc-1_0_0`
- **Adapter:** `wayu-nc-v1` (ชื่อ API/Worker ยังคง v1 แต่รูปแบบ Model Package คือ v2)
- **Runtime:** `wayu-nc` แยก Python Environment จากโปรแกรมหลัก
- **Sample rate:** 24,000 Hz, PCM16 mono ผ่าน Worker Protocol v1
- **ภาษา:** `th`, `en`
- **เสียง:** `f_teen_bright`, `f_young_bright`, `f_young_clear`, `f_young_warm`, `f_mid_clear`, `f_mid_warm`, `f_elderly_soft`, `f_elderly_low`, `m_teen_bright`, `m_young_clear`, `m_mid_warm`, `m_elderly_deep`
- **ป้ายสิทธิ์:** `[NC / NonCommercial]`, `commercial_status=hold`

## วิธีใช้งาน

1. ใช้ Windows Portable **v0.10.1 หรือใหม่กว่า** แพ็กเกจนี้ใช้ไม่ได้กับ v0.10.0 ที่ยังปิดการรองรับไฟล์ PyTorch .pth/.pt ใน Native v2
2. ดาวน์โหลดไฟล์ Wayu NC ที่ระบุข้างต้นจาก Release เดียวกันไปเก็บที่ใดก็ได้
3. เปิดโปรแกรม → **ตั้งค่า → Model Packages → ติดตั้งโมเดล** แล้วเลือกไฟล์ `.vwmodel` ที่ดาวน์โหลดมา การติดตั้งตรวจชนิดไฟล์/Manifest/SHA-256/ต้นทาง/สิทธิ์ก่อนนำไปลงใน `models/universal/v2/tts/wayu-paxa-edge-nc/1.0.0`
4. หาก Wayu Runtime ยังไม่พร้อม เปิด PowerShell ที่โฟลเดอร์ Portable แล้วติดตั้งแบบยืนยันเอง **สำหรับ v0.10.2 ขึ้นไป** (ตัวเลือก `-AcceptProviderTerms` และ `-AcknowledgeNonCommercial` ยังไม่มีในไฟล์ Release v0.10.1 ที่เผยแพร่ไปก่อนหน้า):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Install-WayuWorker.ps1 -AcceptProviderTerms -AcknowledgeNonCommercial
```

ข้อควรระวัง: **Wayu Runtime ยังไม่ได้มี Verified Offline Wheelhouse** เนื่องจาก Dependencies ของ Worker มี Git URL และ Direct URL (รวมถึง `wayu-tts-inference`, โมเดลภาษา spaCy) จึงอาจต้องใช้อินเทอร์เน็ตและเครื่องมือพัฒนาตาม Dependencies; ไม่ควรเข้าใจว่าติดตั้ง Offline ได้เหมือน Sherpa/PyThaiTTS/M2M100. ติดตั้งเฉพาะเมื่อยอมรับให้รัน Dependencies จากแหล่งที่อยู่ใน Recipe ที่ตรวจสอบแล้ว
5. เลือก Engine ชื่อ **[NC / NonCommercial] Wayu Paxa Edge — Thai / English — 12 voices**, เลือก Voice และทดสอบอ่านข้อความ การติดตั้ง v2 ไม่ลบหรือติดตั้งทับโปรเจกต์ Personal Wayu รุ่นเดิมโดยอัตโนมัติ

## ความปลอดภัยของไฟล์ .pth/.pt

ไฟล์ PyTorch `.pth` / `.pt` อาจเป็น Serialized Pickle ซึ่งมีความเสี่ยงที่จะรันโค้ดระหว่างการโหลด **โปรแกรมจึงยังห้ามไฟล์เหล่านี้ใน Native v2 ทั่วไป** ยกเว้น Wayu Paxa Edge รุ่นที่ระบุไว้เท่านั้น โดยมีเงื่อนไขดังนี้:

- ประเภท `tts`, Package ID/Version, 12 Voice ID, Paths, SHA-256 ของน้ำหนักโมเดล, Source URL และ Revision ต้องตรงกับ **First-party Pinned Table** ใน `wayu_native_trust.py`
- License ต้องตรงกับ **CC-BY-NC-4.0** และ `review_status=hold` ไม่อนุญาตให้เปลี่ยนเป็น MIT หรือ cleared
- Installer ตรวจ Hash ขณะอ่าน Archive, ตรวจสิทธิ์/ต้นทางอีกครั้งก่อนสลับโฟลเดอร์ และตรวจน้ำหนักทุกรายการซ้ำใน **Isolated Worker** ก่อนโหลด PyTorch
- ห้ามไฟล์ `.py`, `.dll`, `.exe` หรือ `.pkl` และไฟล์ Pickle อื่นที่ไม่มีอยู่ใน Allowlist ของ Wayu
- ไม่มี Model Package ใดระบุคำสั่งติดตั้ง `pip`, Shell หรือ Worker แบบใหม่จาก Archive ได้

**ข้อจำกัด:** การตรึง Hash ลดความเสี่ยงไฟล์ถูกปลอมแปลง แต่ไม่เท่ากับการตรวจว่าต้นฉบับไม่มีช่องโหว่ และ Python Worker ไม่ใช่ OS-level Sandbox

## สิทธิ์/ต้นทาง

- ต้นทาง: https://huggingface.co/wayu-ai/wayu-paxa-tts-edge
- Revision ที่ตรึง: `8196688df56a8d08ccfa186505343adff412ab6b`
- License: https://creativecommons.org/licenses/by-nc/4.0/legalcode.en
- Upstream acceptable-use: https://www.wayuresearch.org/terms#acceptable-use
- Attribution: Kunat Pipatanakul, Potsawee Manakul, Warit Sirichotedumrong, Sittipong Sripaisarnmongkol, Pakorn Nathong, Phatrasek Jirabovonvisut
- เอกสารในแพ็กเกจ: `README.md`, `legal/license.txt`, `legal/attribution.md`, `legal/acceptable-use.txt`, `legal/rights.json` และ Manifest/SHA-256

โมเดลและเสียง 12 เสียงต้นฉบับไม่มีการแก้ไข; เปลี่ยนเฉพาะรูปแบบบรรจุเป็น Native v2 และข้อมูลอธิบาย/สิทธิ์ ผู้ใช้ต้องปฏิบัติตามสิทธิ์เจ้าของโมเดลและเงื่อนไขการใช้งานเสียงสังเคราะห์

## ผลทดสอบ

- ตรวจไฟล์ต้นฉบับตรง Hash ที่ตรึงครบ 14 ไฟล์ (`config.json`, `model.pth` และเสียง `.pt` 12 เสียง)
- การติดตั้ง Native v2 ลงแยกจากโมเดล/Runtime เดิมผ่าน
- Engine Registry เห็น 12 เสียง, Thai/English และ `commercial_status=hold`
- Isolated Wayu Worker สร้างเสียงภาษาไทยจริงจากแพ็กเกจ Native v2 สำเร็จ **63,600 bytes PCM16**
- ทดสอบปฏิเสธไฟล์น้ำหนักที่ถูกแก้ไข, Extra Pickle, Wrong Adapter/Version และการแอบเปลี่ยนสิทธิ์เป็น MIT

**ยังไม่ยืนยัน:** การย้ายไปติดตั้ง Wayu Runtime บนเครื่อง Windows ใหม่ที่ไม่เคยติดตั้ง Dependencies มาก่อน และคุณภาพเสียง/ความถูกต้องในการอ่านข้อความทดสอบหลายภาษา
