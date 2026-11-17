# Managed Runtime Pool — Phase B (Source หลัง v0.9.5)

**สถานะ:** โค้ดและชุดทดสอบใน Source; ยังไม่ได้รวมใน Windows Portable Release ใหม่

## จุดประสงค์

ระบบ Native Universal `.vwmodel v2` แยก **Model Assets**, **Trusted Adapter** และ **Runtime** ออกจากกัน การติดตั้งแพ็กเกจข้อมูลไม่ได้ให้สิทธิ์รันโค้ดจาก ZIP โดยอัตโนมัติ

ใน Windows Virtual Environment (`venv`) ไม่ควรถูกมองว่าเคลื่อนย้ายไปไดรฟ์ใหม่แล้วพร้อมทำงานเสมอ จึงเพิ่มระบบตรวจสุขภาพและซ่อมแบบ Offline โดยไม่แก้โมเดลหรือไฟล์ตั้งค่า

## Runtime Health Check

เรียก `GET /v1/runtimes` หรือเปิด Runtime Registry ในหน้าโปรแกรม แต่ละ Runtime แสดง `health_state`, `health`, `repair_required`, `runtime_fingerprint` และ `repair.state`

| สถานะ | ความหมาย |
|---|---|
| `ready` | Environment ผ่านการตรวจและมีข้อมูลพาธติดตั้ง |
| `legacy-unpinned` | Runtime รุ่นเดิมยังใช้งานได้ แต่ไม่มีข้อมูลพาธที่บันทึกไว้สำหรับตรวจการย้าย |
| `relocated` | Runtime ที่มีข้อมูลพาธถูกย้ายไปตำแหน่งอื่น |
| `recipe-changed` | SHA-256 ของ Trusted Requirements ไม่ตรงกับที่ใช้ติดตั้ง |
| `python-abi-mismatch` | `pyvenv.cfg` ระบุ Python ไม่ตรงกับ ABI ที่รองรับ (ปัจจุบัน 3.11) |
| `base-python-missing` | ไม่พบโฟลเดอร์ Python ต้นทางที่ `pyvenv.cfg` อ้างอิง |
| `incomplete` | ไฟล์ Python/Marker/Configuration ไม่ครบหรืออ่านไม่ได้ |
| `not-installed` | ไม่มี Runtime นั้น |
| `unsafe-environment` | ตรวจพบโฟลเดอร์ที่ไม่อยู่ในขอบเขตที่จัดการหรือมีการเปลี่ยนเส้นทางที่ไม่ปลอดภัย |

การตรวจ Health เป็น **read-only** ไม่สั่งรัน Python ไม่ดาวน์โหลดไฟล์ และไม่เปลี่ยนโฟลเดอร์ที่ติดตั้ง เมื่อระบบรุ่นใหม่ติดตั้ง Runtime สำเร็จ Marker จะบันทึกพาธโฟลเดอร์โปรแกรมและ Hash ของ Recipe ด้วย

**ข้อจำกัด:** Marker รุ่นเดิมไม่มีพาธต้นทาง จึงรายงาน `legacy-unpinned` และไม่สามารถยืนยันจาก Marker เพียงอย่างเดียวว่าเคยย้ายพาธมาแล้ว การตรวจฐาน Python และ ABI ยังช่วยตรวจได้บางกรณี

## ซ่อม Runtime แบบ Offline

เมื่อ Health รายงาน `repair_required=true` จะมีปุ่ม **ซ่อมจาก uv cache (Offline)** ใน Runtime Registry

1. ผู้ใช้กดยืนยันการซ่อมโดยระบุเฉพาะ Runtime ที่ลงทะเบียนไว้แล้ว
2. Server ตรวจ Same-Origin, Header แสดงเจตนา, `id`, `expected_fingerprint` และ `confirm_repair=true`; ไม่รับพาธ คำสั่ง Shell URL หรือ Dependencies จาก Browser
3. ใช้ Trusted Recipe ที่มากับ Source และ `uv --offline` สร้าง `venv` ใหม่ในโฟลเดอร์ Staging ของ Runtime นั้นเท่านั้น
4. ติดตั้ง Dependencies จากแคชที่มีอยู่, ตรวจ `uv pip check`, ตรวจ Python ABI/Marker และตรวจ Imports เพิ่มเติมสำหรับ M2M100
5. เมื่อผ่านทั้งหมด จึงหยุดเฉพาะ Worker ที่เกี่ยวข้อง สลับโฟลเดอร์แบบ Rename และคืนค่า Runtime เดิมถ้าสลับไม่สำเร็จ

ถ้าแคชไม่มี Wheels ครบ การซ่อม **จะไม่ดาวน์โหลด** และอาจล้มเหลว โดยไม่ลบ Runtime เดิม โฟลเดอร์ Models, User Settings, Presets และ Translation Prompts ไม่ถูกแตะต้อง

ระบบซ่อมนี้ไม่ใช่การรับรองว่า Runtime ทุกชนิดสามารถย้ายแล้วใช้ได้ทันที หลังซ่อมยังต้องทดลอง Inference จริงบนเครื่องปลายทาง รวมถึงตรวจสิทธิ์ License ของโมเดลแต่ละตัว

## ข้อจำกัดปัจจุบันและแผนถัดไป

- Runtime เดิมที่เป็น `legacy-unpinned` ยังไม่ได้ย้ายสถานะเป็น Marker ใหม่โดยอัตโนมัติ เพื่อไม่บันทึกพาธใหม่เป็นต้นทางเทียม
- **Phase C:** เพิ่ม Offline Verified Wheelhouse ใน Source แล้ว (พร้อมชุดจริง Sherpa/PyThaiTTS/M2M100); Vachana/Kokoro มี Draft ที่ทดสอบผ่านแต่ยังต้องตรวจสิทธิ์ก่อน Release · [คู่มือ Phase C](VERIFIED_WHEELHOUSE_TH.md)
- **Phase D:** Adapter SDK, External Code Signing และการรองรับชนิดโมเดลเพิ่ม
- M2M100 ยังมีข้อจำกัด RAM/Commit/Paging File ของเครื่องในการโหลดน้ำหนัก 418M; สถานะ Runtime Ready **ไม่ได้หมายความว่าทดสอบการแปลจริงผ่านแล้ว**

ยังไม่มีการสั่ง Repair จริงกับ Runtime ทั้ง 6 ตัวของเครื่องทดสอบในช่วงการพัฒนานี้ เพื่อหลีกเลี่ยงการดาวน์โหลด/ใช้ทรัพยากรและเปลี่ยนสภาพแวดล้อมโดยไม่จำเป็น
