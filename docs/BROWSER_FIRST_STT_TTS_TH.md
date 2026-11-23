# ทิศทาง Browser-first ของ VoxWeaveTTS และ VoxWeaveSTT

## เป้าหมาย

**VoxWeaveTTS** และ **VoxWeaveSTT** ใช้ Core เป็นเจ้าของการประมวลผล การรับข้อมูล คิว และสถานะทั้งหมด ส่วนหน้าเว็บใน Browser เป็นหน้าควบคุมหลัก ไม่ผูกการทำงานระยะยาวกับการโฟกัสแท็บหรือการเปิด Browser ค้างไว้

- **VoxWeaveTTS:** รักษา Core-owned Source, Queue, Translation/AI, Playback (เมื่อเลือก Computer mode) และ REST/SSE; หน้าเว็บเป็นตัวควบคุมและอ่านสถานะจริงจาก Core
- **VoxWeaveSTT:** ใช้ Local Web UI บน `127.0.0.1:8766` ควบคุม STT และเปิด/ปิด HTTPS LAN Gateway ผ่านหน้าเว็บ Local ได้ โดยไม่ต้องมีโปรแกรม Windows Studio เปิดแสดง
- **VoxWeaveSTT-Client:** พักการพัฒนา Desktop Remote Client ไว้ก่อน; รักษารุ่นเดิมเพื่อความเข้ากันได้ ไม่เพิ่มฟีเจอร์ใหม่ในรุ่น Browser-first
- ไม่เพิ่ม Poller/Worker ที่ Browser ซ้ำกับ Core; การรีเฟรชหน้าเว็บต้องไม่ทำให้ Source เริ่มใหม่หรือเกิดการสร้างงานเสียงซ้ำ

## การเชื่อมต่อ STT API กับ TTS

- **STT Core และ TTS Core อยู่เครื่องเดียวกัน:** ใช้ IP `127.0.0.1`, Port `8766`; ไม่ต้องเปิด HTTPS LAN หรือกรอก PIN/Fingerprint
- **STT Core อยู่คนละเครื่อง:** ใช้ HTTPS LAN Gateway ของ STT และ Fingerprint Pinning ใน TTS Core ก่อนส่ง PIN ไม่เปลี่ยนเป็น HTTP ธรรมดา
- ชื่อผู้ใช้/รหัสผ่านที่กำหนดใน `.cmd` ของ VoxWeaveSTT ใช้สำหรับ **Remote Browser** ที่ล็อกอินผ่าน HTTPS เท่านั้น ไม่ใช่การยกเลิกการตรวจใบรับรอง TLS ในการเชื่อมต่อ Core-to-Core
- ข้อความถอดเสียง `transcript.final` จาก STT ใช้ Source Pipeline และ Speech Queue ของ VoxWeaveTTS Core ตามเดิม

## การจัดลำดับพัฒนา

1. ปรับความถูกต้องและการหยุด/เริ่มของ Core รวมถึงสถานะที่ Web UI แสดงหลัง Refresh
2. เพิ่มฟีเจอร์ใน Web UI ที่ควบคุม Core ด้วย API เดิม โดยไม่สร้างงานซ้ำใน Browser
3. เพิ่มความสะดวกในการตั้งค่าระบบ LAN และยืนยันตัวตนตามนโยบายความปลอดภัย
4. พิจารณา Desktop Client ใหม่เมื่อจำเป็นจริง ๆ เท่านั้น
