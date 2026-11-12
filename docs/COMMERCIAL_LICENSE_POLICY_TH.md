# Commercial-First License Policy — VoxWeaveTTS

> กำหนดนโยบาย: 10 พฤศจิกายน 2026 · **เอกสารนโยบายและการประเมินเบื้องต้น ไม่ใช่หนังสือรับรองทางกฎหมาย**
>
> เป้าหมาย: สามารถนำ VoxWeaveTTS ไปใช้ใน YouTube ที่หารายได้, ไลฟ์สด, API แบบชำระเงิน, โปรแกรมขาย และใช้งานภายในธุรกิจได้โดยลดความเสี่ยงด้านสิทธิ์ให้มากที่สุด

## อัปเดตสำหรับการแจก Model Packages แยกจากโปรแกรม (13 พฤศจิกายน 2026)

สำหรับ **GitHub Release ของ Model Packages ที่ให้ผู้ใช้เลือกดาวน์โหลดเอง** ให้แยกจากนโยบาย "รับรองใช้เชิงพาณิชย์" ของตัวโปรแกรมหลัก: สามารถเผยแพร่ต่อได้ตาม **สิทธิ์ที่ผู้เผยแพร่ต้นทางระบุกับไฟล์น้ำหนักจริง** โดยต้องแนบ License/NOTICE, ข้อมูลแหล่งที่มาแบบตรึง Revision, SHA-256 และเครดิตชุดข้อมูลที่ตรวจพบ รวมถึงแจ้งความไม่แน่ชัดของสิทธิ์เสียง/ข้อมูลฝึกอย่างชัดเจน **ไม่ใช้ข้อความปฏิเสธการรับผิดชอบเพื่อทดแทนสิทธิ์การแจกจ่าย** และยังไม่จัดสถานะ Commercial-Cleared เมื่อหลักฐานไม่ครบ

- VachanaTTS: Model Card ของ `VIZINTZOR/VachanaTTS` ระบุ **MIT** สำหรับรุ่นที่ใช้; ข้อมูลฝึกของแต่ละเสียงไม่แจกแจงครบ จึงคง `review_required` ใน Manifest
- FastThaiG2P/Kokoro Thai Som: Repository และ Release ของ `awslabs/FastThaiG2P` มี Apache-2.0 พร้อม `NOTICE`; Som TTS Dataset ระบุ **CC BY 4.0** ซึ่งต้องให้เครดิต ผู้ใช้งานต้องอ่าน License/Attribution ที่อยู่ในแพ็กเกจ และยังไม่มีการตรวจสิทธิ์เสียงทุกองค์ประกอบโดยอิสระ

รายการสินทรัพย์ที่แจกจริงอยู่ใน [Model Packages Catalog](../model-packs/README_TH.md) และ [ข้อมูล SHA-256](../model-packs/catalog.json) นโยบาย Commercial-safe-first ด้านล่างยังใช้กับ **การรับรองเชิงพาณิชย์และการบันเดิลเป็นโมเดลหลัก** ไม่ใช่การเปลี่ยน MIT/Apache/CC BY เป็นเงื่อนไขห้ามใช้เชิงพาณิชย์

## นโยบายหลัก

**Default = Commercial-safe-first / Fail-closed สำหรับการแจกจ่ายและการประกาศว่าใช้เชิงพาณิชย์ได้**

1. **ห้ามสรุปจาก License ของซอร์สโค้ดไปยัง Model Weights** ทุก Engine ต้องมีหลักฐานแยกสำหรับ: source code, model weights, voicepack/reference audio, datasets ที่นำเข้ามาฝึก/ดัดแปลง, dependencies, ตัวติดตั้ง และสิทธิ์ในการแจกจ่ายโมเดล
2. สำหรับ **Engine/โมเดลหลักที่จะแนะนำและแจกจ่าย** ให้รับเฉพาะสิทธิ์แบบ permissive ที่ยืนยันชัด (เช่น MIT, Apache-2.0, BSD, CC0) หรือมีหนังสืออนุญาตเชิงพาณิชย์เพิ่มเติม โดยปฏิบัติตาม NOTICE/Attribution, ความเกี่ยวข้องของ Software Patents และสิทธิ์อื่นตามจริง
3. หากมี **NC, Unknown, Custom License, Noncommercial-only, research-only** หรือข้อมูลยังไม่พอ ให้ทำเครื่องหมาย **REVIEW_REQUIRED / HOLD** และไม่ใส่โมเดลนั้นใน Commercial/Portable Distribution จนกว่าจะตรวจครบหรือได้รับอนุญาต
4. แม้ **CC BY-SA 4.0 อนุญาตเชิงพาณิชย์** แต่มี ShareAlike; สำหรับเป้าหมายลดภาระ Compliance จึงกำหนด **HOLD** กับโมเดล/Adapter ที่มี ShareAlike จนกว่าจะตัดสินใจรับเงื่อนไขโดยตั้งใจ แยกจากคำว่า "ใช้เชิงพาณิชย์ไม่ได้"
5. ไฟล์เสียงต้นฉบับ/Reference Voice ต้องเป็นเสียงที่เจ้าของมีสิทธิ์ใช้หรือได้รับการยินยอม/อนุญาตที่เหมาะสม **ห้ามใช้เสียงคนอื่นโดยไม่มีสิทธิ์** การเป็น MIT/Apache ของโมเดลไม่ให้สิทธิ์เหนือเสียง/ภาพ/ชื่อของบุคคลอื่น
6. แหล่งข้อความ เช่น นิยายที่นำมาอ่าน, ข้อความแชทที่เผยแพร่และตัวอักษร, เอฟเฟกต์เสียง, พจนานุกรมและข้อมูลประกอบ ต้องตรวจสิทธิ์แยก; การมี TTS เชิงพาณิชย์ได้ ไม่ได้ให้สิทธิ์นำเนื้อหาที่มีลิขสิทธิ์มาเผยแพร่
7. **ไม่รวมไฟล์โมเดล, เสียงส่วนตัว, datasets หรือ Binary FFmpeg/อื่น ๆ ลง Public GitHub/Portable ZIP โดยอัตโนมัติ** ทำ License Audit ก่อน Release ทุกครั้ง
8. ไม่ให้ UI/API แสดงว่า Engine **"Commercial Cleared"** จนกว่าจะมีเอกสารหลักฐาน, upstream revision/hash, license notices และผล dependency audit ที่เพียงพอ

## สถานะการคัดเลือก ณ วันที่ตรวจสอบ

| ชื่อ | License ที่มีหลักฐาน | สถานะเชิงนโยบาย | ข้อพิจารณา |
|---|---|---|---|
| **VoxCPM2 (openbmb)** | ผู้พัฒนาประกาศทั้ง **โค้ดและโมเดล Apache-2.0** | **Candidate หลัก** | เป็นตัวเลือกสำหรับ Voice Cloning/LoRA; ก่อนจำหน่ายหรือแจกต้อง Audit dependencies/เสียง/ข้อมูลที่ใช้ฝึกของผู้ใช้ และตรวจข้อกำหนด upstream revision จริง |
| **MakHam Paradee** | Model Card **Apache-2.0**; Dataset **CC BY 4.0** | **Candidate (ต้องจัดเครดิต/ตรวจ artifact)** | Apache และ CC BY ต่างอนุญาตการค้า แต่ต้องตรวจ exact checkpoint, notices, attribution และ dependencies ก่อนแจก |
| **FastThaiG2P / Thai Kokoro release assets** | PyThaiTTS code Apache-2.0; ยังต้องตรวจ **License สำหรับไฟล์ ONNX/voicepack release ที่ใช้อยู่** แยก | **Review required สำหรับการแจก** | การที่ library code Apache ไม่พอจะรับรอง model assets ของ v0.3.0 |
| **Lunarlist/tts-thai** | Hugging Face model card ระบุ **MIT** | **Candidate สำหรับ Audit เพิ่ม** | ต้องยืนยันว่า ONNX conversion/weights/voice assets ใน Adapter มีสิทธิ์ตรงกันและต้นฉบับไม่ขัดแย้ง |
| **SiangTTS VoxCPM2 Thai LoRA** | Adapter weights **CC BY-SA 4.0**; base Apache-2.0 | **Hold ตามนโยบายแบบอนุรักษ์นิยม** | *Commercial allowed* ตาม BY-SA แต่ต้องพิจารณา ShareAlike; ไม่ใช่ NonCommercial |
| **ThonburianTTS weights** | **CC BY-NC-SA 4.0** | **Exclude** | มีข้อจำกัด NonCommercial; ใช้เชิงพาณิชย์ต้องขออนุญาตเพิ่ม |
| **VachanaTTS / KhanomTan / Other community models** | ยังไม่ตรวจครบถึงน้ำหนักโมเดลหรือชุดเสียง | **Hold** | ห้ามอนุมานว่าผ่านเพราะ Open-source library หรือแสดงเสียงตัวอย่างได้ |
| **RVC** | Source code MIT (สำหรับส่วนที่ตรวจ); น้ำหนักโมเดลเสริม/ฐานและชุดข้อมูลขึ้นกับที่ใช้จริง | **Framework Only / Hold pretrained assets** | หากใช้ข้อมูลเสียงที่เป็นสิทธิ์ของตนเองยังต้อง Audit dependency/model initialization |
| **VITS** | Framework code MIT; trained checkpoint ขึ้นกับ provenance | **Framework Only** | ต้องฝึกด้วย datasets ที่มีสิทธิ์เชิงพาณิชย์ชัดเจน |

**สถานะ Candidate ไม่ได้แปลว่า Commercial-Cleared แล้ว** เนื่องจากยังไม่ได้ Audit ไฟล์ที่แพ็กจริงทั้งหมด และอาจมีข้อจำกัดจากข้อกำหนดส่วนบุคคล/แพลตฟอร์มที่ License โมเดลไม่ครอบคลุม

## Source links และหลักฐานที่ต้องบันทึก

- VoxCPM2 upstream model/code + Apache 2.0: https://openbmb.cn/en/model/voxcpm-2
- VoxCPM2 Fine-tuning: https://voxcpm.readthedocs.io/en/latest/finetuning/finetune.html
- MakHamTTS model card: https://huggingface.co/pythainlp/MakHamTTS
- MakHamTTS dataset license CC BY 4.0: https://huggingface.co/datasets/pythainlp/MakHamTTS-dataset
- PyThaiTTS code Apache 2.0: https://github.com/PyThaiNLP/PyThaiTTS
- FastThaiG2P upstream: https://github.com/awslabs/FastThaiG2P
- SiangTTS adapter license: https://huggingface.co/dubbing-ai/SiangTTS-VoxCPM2-Thai-LoRA/blob/main/LICENSE
- CC BY-SA (commercial use allowed with ShareAlike): https://creativecommons.org/licenses/by-sa/4.0/
- CC BY-NC-SA (noncommercial): https://creativecommons.org/licenses/by-nc-sa/4.0/

เก็บสำเนา/Hash/วันที่ดึง License ของเวอร์ชันที่นำมาแจกจริงเพิ่มเติม เพื่อป้องกันการอ้างข้อมูลที่เปลี่ยนหลังจากติดตั้ง

## Distribution / Training Release Gate

ก่อนออก GitHub Release, Portable ZIP หรือจำหน่าย ให้ผ่านรายการต่อไปนี้:

- [ ] Code license ของโปรเจกต์และ dependencies พร้อม NOTICE/ATTRIBUTION
- [ ] Model/voicepack/checkpoint แต่ละไฟล์มี License ต้นทาง, version/revision, SHA-256 ที่ชัด
- [ ] Dataset และสิทธิ์เสียงใช้ฝึก Fine-tune มีหลักฐาน/ความยินยอมที่เหมาะสม; ไม่ดึงข้อมูลจากแหล่งที่ห้ามใช้
- [ ] ตรวจการใช้ FFmpeg/Rubber Band และว่าชุด Binary ที่จะแจกเป็น LGPL/GPL หรือมี Commercial License ใดบ้าง (การเรียกผ่าน subprocess ไม่ใช่หลักฐานว่าแจกได้โดยไม่มีเงื่อนไข)
- [ ] ตรวจ Runtime Libraries, Fonts, Samples และ Assets ที่รวมไปใน Installer
- [ ] ตรวจขอบเขตการใช้เสียงสังเคราะห์และสิทธิ์ของข้อความ/ชื่อ/บุคลิกเสียงที่เผยแพร่
- [ ] มี THIRD_PARTY_NOTICES/License Manifest ต่อ build จริง พร้อมตัวเลือกที่ปิดไว้เมื่อสถานะเป็น Unknown/Hold
- [ ] ทดสอบบนเครื่องสะอาดและตรวจว่า ZIP ไม่เผลอรวมเสียง/Token/ไฟล์ส่วนตัวของผู้ใช้

## การตัดสินใจในการพัฒนาถัดไป

- ใช้ **VoxCPM2 (Apache-2.0)** เป็น Engine ทดลอง Voice Cloning/Fine-tuning รายแรกโดยแยกตัวติดตั้งและยังไม่แพ็กให้ผู้ใช้ทั่วไป
- **MakHam Paradee** อยู่ในกลุ่ม Candidate สำหรับการค้า ไม่จำเป็นต้องลบจาก Developer Prototype; ต้องตรวจ Credits/Artifacts/Dependency ก่อนประกาศว่าสามารถแจกใน Commercial Bundle ได้
- คง FastThaiG2P เพื่อทดสอบใน Developer Prototype แต่ **ยังไม่เคลียร์ไฟล์ weights/voicepack สำหรับการนำไปจำหน่ายหรือแพ็กแจก** จนกว่าจะยืนยัน
- ไม่ดาวน์โหลด/แพ็ก SiangTTS, ThonburianTTS หรือโมเดลที่ยังไม่แน่ใจใน Release หลัก
- หากอนาคตต้องเลือกรุ่นอื่น ให้ทำ Audit ก่อนดาวน์โหลด/ผูก Dependency ที่จะแจก แทนการเพิ่ม Engine ตามชื่อหรือตามคะแนนคุณภาพอย่างเดียว

**คำเตือน:** ไม่มีวิธีรับรองได้ว่า "ปลอดภัยจากข้อพิพาท 100%" เพียงเพราะมี License เปิดเผย เอกสารนี้เป็น License Policy ที่ลดความเสี่ยง ไม่ใช่การให้ความเห็นทางกฎหมายเฉพาะกรณี การจำหน่ายจริงควรตรวจความครบถ้วนตามกฎหมาย/สัญญาที่เกี่ยวข้อง
