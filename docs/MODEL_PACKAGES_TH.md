# VoxWeaveTTS — Model Packages (.vwmodel)

สถานะ: โปรแกรมรองรับ .vwmodel ตั้งแต่ v0.4.2 · **แพ็กเกจทดลองที่เผยแพร่ต่อภายใต้สิทธิ์ต้นทาง** ดู [Model Packages Catalog](../model-packs/README_TH.md) และ [Manifest/Hash](../model-packs/catalog.json) · ไม่ใช่ Model Store ที่รับรองสิทธิ์ทั้งหมด

## แนวคิด

แยกตัวโปรแกรมหลัก (Engine Adapter) ออกจากข้อมูลโมเดลและเสียง (Model Package)

- โปรแกรมหลักมี Engine Adapter ที่เชื่อถือได้และ Dependencies ของแต่ละ Engine
- Model Package เป็น ZIP นามสกุล .vwmodel ที่มี Manifest และไฟล์โมเดลเท่านั้น ไม่รับ Python, DLL, EXE หรือสคริปต์
- ติดตั้งหลายแพ็กเกจ หลายเวอร์ชัน และหลายเสียงพร้อมกันได้โดยไม่เขียนทับกัน แต่ละแพ็กเกจมี Engine ID ที่แยกกัน
- โมเดลสถาปัตยกรรมใหม่ต้องมี Engine Adapter ที่รองรับในโปรแกรมก่อน การเปลี่ยนชื่อโมเดลไม่ได้ทำให้รันได้
- ใช้กฎคำอ่าน คิวเสียง OBS Subtitle ร่วมกันเหมือนเดิม

โฟลเดอร์ติดตั้งทั้งหมดเป็น Relative Path ย้ายไดรฟ์พร้อมโปรแกรมได้:

    models/packages/<package_id>/<version>/
      manifest.json
      speaker_config.json
      voices/th_f_1.onnx
      voices/th_f_2.onnx

## ติดตั้งจากหน้าโปรแกรม (Firefox / Chrome)

1. เปิดแท็บ **ตั้งค่า** จากเมนูด้านซ้าย แล้วขยายส่วน **จัดการ Model Packages**
2. กด ติดตั้ง Model Package (.vwmodel) เพื่อเปิดหน้าต่างเลือกไฟล์ของ Windows
3. โปรแกรมตรวจ Engine ที่รองรับ รูปแบบ Manifest และ SHA-256 ของทุกไฟล์ก่อนติดตั้ง ไม่ทับรุ่นเดิม
4. ดูรายชื่อแพ็กเกจ เสียง Dependencies และไลเซนส์ที่ระบุไว้
5. เลือก TTS Engine ของแพ็กเกจ จากนั้นเลือกเสียงผู้พูดและทดลองอ่าน
6. ถอนการติดตั้งได้เฉพาะแพ็กเกจและเวอร์ชันที่เลือก โดยกดยืนยันก่อน

ไม่ต้องกรอกรหัสผ่าน ไม่อัปโหลดไฟล์โมเดลไปยังเซิร์ฟเวอร์ภายนอก ตัวเลือกไฟล์และการติดตั้งทำงานบน Windows เครื่องเดียวกันเท่านั้น

หาก Engine ขึ้นว่า Runtime ยังไม่พร้อม แสดงว่าโปรแกรมยังขาด Dependencies ที่ Manifest ระบุ การติดตั้งแพ็กเกจไม่ดาวน์โหลดหรือติดตั้งไลบรารีเพิ่มเติมโดยอัตโนมัติเพื่อความปลอดภัย

## คำสั่งสำหรับนักพัฒนา

ในโฟลเดอร์โปรเจกต์ กำหนด PYTHONPATH=src ก่อนเรียกคำสั่ง:

    python -m voxweavetts.model_packages list
    python -m voxweavetts.model_packages install "T:\Models\my-model.vwmodel"
    python -m voxweavetts.model_packages remove my-model 1.0.0

หากติดตั้งจาก CLI ขณะที่เซิร์ฟเวอร์เปิดอยู่ ให้รีสตาร์ต Backend เพื่อให้รายการ Engine รีโหลดใหม่ การติดตั้งผ่านหน้าโปรแกรมจะรีเฟรชรายการหลังสำเร็จโดยตรง

## Manifest v1

ไฟล์ .vwmodel ต้องมี manifest.json เป็นรายการแรกใน ZIP โดยมีข้อมูลดังนี้:

- format: voxweavetts.model-package
- format_version: 1
- package_id: ชื่อแพ็กเกจที่ไม่ซ้ำ เช่น vachana-thai-four-voices
- version: เลขเวอร์ชัน เช่น 1.0.0
- title: ชื่อแสดงผลในโปรแกรม
- engine_adapter: ขณะนี้รองรับ `vachana-onnx-v1` และ `fastthaig2p-kokoro-v1`
- language, sample_rate: ภาษาและอัตราสุ่มเสียงที่ Adapter รองรับ
- voices: รายชื่อ ID เสียง ชื่อแสดง และไฟล์ ONNX ของแต่ละเสียง (Vachana) หรือ `.npy` Voicepack (FastThaiG2P)
- files: รายชื่อไฟล์จริงทุกไฟล์ พร้อมขนาดเป็นไบต์ และ SHA-256 แบบ 64 อักขระ
- license: SPDX ID, URL แหล่งที่มาของไลเซนส์, เครดิต และ review_status
- source: URL ผู้เผยแพร่โมเดลและ Revision
- dependencies: ชื่อไลบรารีที่ Engine ต้องใช้ (แสดงไว้ ไม่ติดตั้งอัตโนมัติ)

ตัวติดตั้งปฏิเสธไฟล์ที่ไม่อยู่ใน Manifest, เส้นทางข้ามโฟลเดอร์, ZIP Symlink, ไฟล์สคริปต์, ขนาดไม่ตรง, SHA-256 ไม่ตรง, เวอร์ชันเดิมที่มีอยู่แล้ว และโมเดลที่ไม่มี Adapter รองรับ การติดตั้งจะเสร็จเป็นชุด ไม่ทิ้งโมเดลที่ติดตั้งค้างครึ่งหนึ่ง

## Vachana Thai 4 Voices — ตัวอย่างที่ทดสอบแล้ว

จากโฟลเดอร์โปรเจกต์ที่มีโมเดลใน models/vachana/

    python -m voxweavetts.model_packages pack-vachana

ได้ไฟล์ในเครื่อง:

    dist/ModelPackages/VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel

ประกอบด้วย speaker_config.json และ ONNX 4 เสียง:
หญิง 1 (th_f_1), หญิง 2 (th_f_2), ชาย 1 (th_m_1), ชาย 2 (th_m_2)

ใน Developer Environment ติดตั้งแพ็กเกจนี้แล้วและสร้าง WAV จากทั้งสี่เสียงได้จริง โดยอ่านจาก models/packages/ ไม่ใช่โฟลเดอร์โมเดลเดิม

แหล่งข้อมูล: https://huggingface.co/VIZINTZOR/VachanaTTS
Runtime: vachanatts==0.0.7, onnxruntime, pythainlp, ssg

ไลเซนส์ใน Manifest ระบุ **MIT ตาม Model Card ต้นทาง** และแพ็กเกจมี `legal/license.txt` / `legal/attribution.md` ให้เครดิตผู้เผยแพร่ ส่วน `review_required` หมายถึง **เราไม่ได้ตรวจสอบสิทธิ์ของข้อมูลฝึกและเสียงทั้งหมดโดยอิสระ** ไม่ใช่การเพิ่มเงื่อนไขห้ามแจกต่อจากที่ต้นทางประกาศ แพ็กเกจเสริมมีใน [Model Packages Release](https://github.com/funggier/VoxWeaveTTS/releases/tag/modelpacks-v0.4.2) แยกจาก Portable หลัก

Windows Portable v0.4.2 มี Engine Adapter และ Runtime ที่ต้องตรวจสอบก่อนใช้งาน หากรายการ Engine แสดง Runtime ไม่พร้อม ต้องตรวจ Dependencies ตาม Manifest (ตัวติดตั้งโมเดลไม่รันโค้ดหรือ pip โดยอัตโนมัติ)

## FastThaiG2P Thai Som เป็นแพ็กเกจแยก

สามารถสร้างแพ็กเกจจากโมเดล FastThaiG2P ที่มีอยู่ใน `models/fastthaig2p/` ด้วยคำสั่ง `python -m voxweavetts.model_packages pack-fastthai` จะได้ไฟล์ `dist/ModelPackages/VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` สำหรับติดตั้งแยกผ่าน Model Package Manager โดยใช้ Engine Adapter `fastthaig2p-kokoro-v1` และไฟล์ ONNX + Voicepack .npy

ทดสอบสร้าง WAV ไทยได้ทั้งที่ x1 และ x5 จากแพ็กเกจที่ติดตั้งแล้ว ขณะที่ **Portable หลักบันเดิลเฉพาะน้ำหนัก MakHam Paradee** ไม่รวม FastThaiG2P หรือ Vachana แพ็กเกจ FastThaiG2P ระบุ Apache-2.0 พร้อมต้นฉบับ LICENSE/NOTICE และมีข้อมูลฝึก Som TTS ระบุ CC BY 4.0 โดยเราใส่เครดิตไว้ใน `legal/attribution.md` ไฟล์น้ำหนักเผยแพร่ใน [Model Packages Release](https://github.com/funggier/VoxWeaveTTS/releases/tag/modelpacks-v0.4.2) ตามสิทธิ์ต้นทางที่ระบุ ส่วนสถานะ `review_required` คือยังไม่มีการรับรองสิทธิ์เสียง/ข้อมูลฝึกทุกส่วนโดยอิสระ

## ความปลอดภัยและลิขสิทธิ์

- SHA-256 เป็นการตรวจความสมบูรณ์เทียบกับ Manifest ภายในแพ็กเกจ แต่ไม่ได้พิสูจน์ว่า Manifest มาจากผู้เผยแพร่จริง
- ห้ามถือว่าไฟล์ Manifest ที่อ้าง MIT หรือ Apache-2.0 ได้รับการตรวจสิทธิ์ถูกต้องแล้วโดยอัตโนมัติ ต้องตรวจที่มา ไลเซนส์น้ำหนักโมเดล ข้อมูลฝึก และเครดิตก่อนเผยแพร่
- ติดตั้งเฉพาะไฟล์จากแหล่งที่ไว้ใจได้ ไฟล์ ONNX แม้ไม่ใช่ Python Code ก็ยังถูกประมวลผลด้วย Runtime จึงควรระวังไฟล์จากแหล่งไม่รู้จัก
- ไม่รวมไฟล์เสียงส่วนตัว Credentials และไฟล์ของผู้ใช้อื่นลงในแพ็กเกจ

## อนาคต

สามารถเพิ่ม Adapter สำหรับสถาปัตยกรรมอื่น เช่น Piper, Kokoro, VITS หรือ XTTS โดยกำหนดไฟล์ที่รองรับและโครงสร้างเสียงชัดเจน แพ็กเกจของแต่ละตระกูลสามารถติดตั้งร่วมกันได้ โดยไม่ผูกทุกโมเดลกับ Engine เดียวกัน
