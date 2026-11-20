# VoxWeaveTTS v4 — สำเนาหลักฐานสิทธิ์จากผู้เผยแพร่ต้นทาง

**สถานะ: หลักฐานสำหรับตรวจสอบ ไม่ใช่การอนุมัติการแจกจ่าย**

เอกสารในชุดนี้คัดลอกเป็น **ไฟล์ต้นฉบับโดยไม่แก้ข้อความ** จาก Hugging Face, GitHub ของเจ้าของโมเดล/โค้ด และเว็บไซต์เจ้าของเงื่อนไขการใช้งานอย่างเป็นทางการ เพื่อใช้อ้างอิงสิทธิ์ย้อนหลัง แม้หน้าเว็บต้นทางจะเปลี่ยนแปลงในอนาคต

## ตำแหน่งในโปรเจกต์

| ที่เก็บ | สิ่งที่มี |
| --- | --- |
| \`cache/v4-rights-evidence/upstream/\` | README/Model Card, LICENSE, NOTICE, Model Use Terms และเอกสารประกอบที่คัดลอกจากเจ้าของโมเดล โค้ด และชุดข้อมูล |
| \`cache/v4-rights-evidence/wheel-docs/\` | \`METADATA\`, LICENSE และ NOTICE **จาก Wheel ที่บรรจุอยู่ในแพ็กเกจ v4 จริง** แยกตาม SHA-256 ของ Wheel |
| \`cache/v4-rights-evidence/INDEX.json\` | ดัชนีต้นทาง, Revision, วันที่ดึงข้อมูล, SHA-256, จำนวนไบต์ และพาธสำเนา |
| \`cache/v4-rights-evidence/wheel-index.json\` | ดัชนี SHA-256 Wheel, เอกสาร License/Metadata ภายใน Wheel และพาธสำเนา |
| \`docs/v4_upstream_evidence_index.json\` | **สำเนาดัชนีอ้างอิงสำหรับ Git** ที่ไม่มีเนื้อหาลิขสิทธิ์ของเอกสารต้นทาง แต่มี URL/Revision/SHA-256 พร้อมใช้ตรวจสอบ |
| \`cache/v4-rights-evidence/VoxWeaveTTS-v4-upstream-rights-evidence.zip\` | สำเนาเอกสารทั้งหมดและดัชนีในไฟล์ ZIP เดียวสำหรับเก็บแบบออฟไลน์ |

**ZIP สำหรับอ้างอิง (บันทึกเมื่อ 20 พฤศจิกายน 2026):** ขนาด 1,186,651 ไบต์ · SHA-256 `b0bbec17ec18ca4dc63b0ce1a5dd70558704acf359198f0a59ec4cff386b5341` · ตรวจ CRC และตรวจ SHA-256 ของเอกสารทั้ง 345 ไฟล์ผ่านแล้ว

**สำคัญ:** เอกสารต้นฉบับและ ZIP เก็บไว้ **ในเครื่องผู้พัฒนา** ภายใต้ \`cache/\` ที่ Git Ignore ไม่ได้ Publish เอกสารของบุคคลที่สามขึ้น GitHub โดยไม่ได้ตรวจสิทธิ์การเผยแพร่ตัวเอกสารก่อน ขณะที่ดัชนีที่ไม่มีสำเนาข้อความของบุคคลที่สามสามารถเก็บใน Git ได้

## แหล่งเอกสารอ้างอิง

| รายการ | เอกสารที่เก็บ | เว็บไซต์เจ้าของ |
| --- | --- | --- |
| MakHam / FastThaiG2P | Model Card หลัก + README ของรุ่น FastThaiG2P และ Paradee | https://huggingface.co/pythainlp/MakHamTTS |
| ชุดข้อมูล MakHam | Dataset Card, ประกาศ CC BY 4.0 | https://huggingface.co/datasets/pythainlp/MakHamTTS-dataset |
| ชุดข้อมูล Som | Dataset Card, ประกาศ CC BY 4.0 | https://huggingface.co/datasets/pythainlp/som_tts_dataset |
| Melo Chinese | Model Card (MIT ที่ผู้เผยแพร่ระบุ) | https://huggingface.co/myshell-ai/MeloTTS-Chinese |
| Supertonic 3 | **ต้นฉบับ LICENSE (OpenRAIL-M)** และ Model Card | https://huggingface.co/Supertone/supertonic-3 |
| Kokoro | Model Card และ License Claim (Apache-2.0) | https://huggingface.co/hexgrad/Kokoro-82M |
| Vachana | Model Card (MIT) และ README ของ Source Code ที่เกี่ยวข้อง | https://huggingface.co/VIZINTZOR/VachanaTTS |
| Wayu Paxa Edge NC | Model Card (CC BY-NC 4.0), ประกาศ Acceptable Use และหน้าเงื่อนไขจากผู้เผยแพร่ | https://huggingface.co/wayu-ai/wayu-paxa-tts-edge |
| M2M100 418M | Model Card (MIT) | https://huggingface.co/facebook/m2m100_418M |
| โค้ดอนุมาน PyThaiTTS | README, LICENSE Apache 2.0 และเอกสาร Package | https://github.com/PyThaiNLP/PyThaiTTS |
| FastThaiG2P | README, LICENSE, NOTICE และ Package Metadata | https://github.com/awslabs/FastThaiG2P |
| Paradee | README, LICENSE และ Package Metadata | https://github.com/sahilmahendrakar/paradee |
| sherpa-onnx | README, LICENSE และ Package Metadata | https://github.com/k2-fsa/sherpa-onnx |
| Wayu Inference | README, LICENSE และ Package Metadata | https://github.com/wayu-research/wayu-tts-inference |
| Vachana Python Inference | README; **ไม่มี LICENSE แยกใน Root ที่ต้นทางประกาศในรอบนี้** | https://github.com/VYNCX/VachanaTTS |

สำเนาไฟล์ Hugging Face และ GitHub อ้างอิง **Commit SHA 40 ตัวอักษร** อย่างเจาะจง โดยเก็บ URL \`resolve/<SHA>/...\` และ \`raw.githubusercontent.com/<repo>/<SHA>/...\` ลงดัชนี; ไม่มีการใช้ลิงก์ \`main\` เป็นหลักฐานฉบับคงที่

สำหรับเว็บไซต์เงื่อนไขที่ไม่มี Git Commit (เช่น Wayu Research Terms และ CC BY-NC 4.0 legalcode) เก็บ **Snapshot พร้อมเวลาที่ดาวน์โหลดและ SHA-256** โดยระบุชัดว่าเว็บไซต์อาจเปลี่ยนภายหลังและไม่อ้างว่าเป็น Immutable Source

## ตรวจสอบสำเนาและสร้างชุดอ้างอิงใหม่

บน Windows PowerShell ที่โฟลเดอร์โปรเจกต์:

~~~powershell
# ตรวจ SHA-256 ของทุกสำเนา โดยไม่ติดต่ออินเทอร์เน็ต
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_rights_evidence.py

# ดึงเอกสารต้นทางปัจจุบัน สร้างสำเนาและดัชนีใหม่ รวมเอกสารที่มีอยู่ใน Wheel
.\.venv\Scripts\python.exe -X utf8 scripts\archive_v4_upstream_rights.py --wheels

# ยืนยันความถูกต้องและรวมเป็น ZIP สำหรับ QA (จะไม่เขียนทับ ZIP ที่มีอยู่)
.\.venv\Scripts\python.exe -X utf8 scripts\verify_v4_rights_evidence.py --bundle
~~~

เมื่อยืนยันสิทธิ์ต้องระบุ **ทั้ง URL ต้นทาง, Revision หรือ Timestamp, SHA-256 เอกสาร, ขอบเขต License และชื่อโมเดล/ไลบรารี** ไม่ใช่ดูเฉพาะข้อความ \`License: MIT\` ใน Manifest

## ช่องว่างด้านสิทธิ์ที่ยังต้องตรวจ

1. **Wayu:** น้ำหนักโมเดล CC BY-NC 4.0 จำกัดการใช้เชิงพาณิชย์ แม้โค้ดอนุมานจะเป็น Apache-2.0; หน้า Acceptable Use เป็นต้นทางแยกต่างหาก
2. **Supertonic 3:** มีใบอนุญาต OpenRAIL-M พร้อมข้อจำกัดการใช้งาน ห้ามอ้างว่าเป็น MIT หรือ Apache
3. **Kokoro:** น้ำหนักโมเดล Apache-2.0 แยกจาก GPL/LGPL และ Native Components ของ G2P/Phonemizer
4. **Vachana:** การประกาศ MIT ใน Model Card ไม่ทำให้ \`vachanatts 0.0.7\` Wheel ซึ่งไม่มีข้อมูล License เพียงพอ ได้รับอนุญาตให้แจกจ่ายโดยอัตโนมัติ
5. **ทุกโมเดล:** ยืนยันว่าไฟล์ที่บรรจุจริงใน \`.vwmodel v4\` ตรงกับ Source/License ที่ประกาศ รวมทั้ง Weight, Dataset/Voice Rights และ Wheel ทุกไฟล์

ดูการวิเคราะห์เพิ่มเติมใน [V4_RIGHTS_REVIEW_TH.md](V4_RIGHTS_REVIEW_TH.md)

**Public Release ทั้งแปดแพ็กเกจยังถูก BLOCK** จนกว่าจะมีหลักฐานประกอบครบและผ่านการตรวจสิทธิ์ที่แยกจากระบบติดตั้งโดยผู้ใช้
