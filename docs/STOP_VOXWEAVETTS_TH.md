# Stop-VoxWeaveTTS — หยุดโปรแกรมจริงและคืนหน่วยความจำบน Windows

สำหรับกรณีปิดหน้าต่าง VoxWeaveTTS แล้ว แต่ Python/Worker ที่โหลดโมเดลเสียงยังอยู่ หรือเมื่อเลิกใช้งานโปรแกรมและต้องการคืนทรัพยากรให้ Windows

## วิธีใช้

จากโฟลเดอร์ที่มีโปรแกรม (ไม่ต้องเปิดโปรแกรมก่อน):

- **`Stop-VoxWeaveTTS.cmd`** — หยุดเซิร์ฟเวอร์และ TTS Worker ที่เป็นของโฟลเดอร์ VoxWeaveTTS นี้ พร้อม Process ลูก บังคับปิดแม้ Worker ไม่ตอบสนอง
- **`Stop-Dev.cmd`** — คำสั่งเดียวกันสำหรับชุด Source ที่เปิดด้วย `Start-Dev.cmd`
- **`Stop-Console.cmd`** — ทางลัดที่รวมใน Windows Portable รุ่นที่ Build จาก Source ใหม่ และใช้ร่วมกับ `Start-Console.cmd`
- `Stop-VoxWeaveTTS.cmd -DryRun` — แสดงเฉพาะ PID ที่ตรวจสอบว่าเป็นของโปรเจกต์ก่อนดำเนินการ โดยไม่ปิดอะไรจริง

หรือเรียกจาก PowerShell ได้:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Stop-VoxWeaveTTS.ps1 -ProjectRoot . -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Stop-VoxWeaveTTS.ps1 -ProjectRoot .
```

**พฤติกรรม:** ใช้ `taskkill /T /F` บน Windows เฉพาะต้นไม้ของ Process ที่ยืนยันเจ้าของได้ เซิร์ฟเวอร์ภายในโฟลเดอร์จะถูกปิดและ Windows จะคืนพอร์ตที่ Process นั้นใช้อยู่ เมื่อเลิกทำงาน ระบบปฏิบัติการจะคืนหน่วยความจำที่ Process ใช้อยู่ตามปกติ

## การระบุตัวตนของ Process และความปลอดภัย

- เมื่อ VoxWeaveTTS เริ่มทำงาน จะบันทึก PID และเวลาเริ่ม Process ของเซิร์ฟเวอร์และ Worker ไว้ใน `runtime/processes/*.json` (ไม่ขึ้น Git ไม่รวมใน ZIP)
- แม้หน้าต่างหลักจะปิดผิดปกติ ตัวหยุดสามารถอ่าน Registry นี้เพื่อหา Worker/Launcher ที่เคยถูกเปิดโดยโฟลเดอร์เดียวกัน แต่จะตรวจเวลาสร้าง Process จาก Windows อีกครั้งเพื่อไม่ให้ PID ที่ถูกนำไปใช้ซ้ำทำให้ปิดโปรแกรมอื่น
- มีการค้นหาแบบเข้มงวดเพิ่มเติมสำหรับโปรแกรมรุ่นก่อนที่ไม่มี PID Registry โดยระบุ Interpreter หรือ Executable ภายใต้โฟลเดอร์โปรเจกต์นี้เท่านั้น
- ไม่ลบ Models, Presets, Settings, Cache, Voices, Output หรือ Log และไม่จำเป็นต้องย้ายโปรแกรมไปไว้บนไดรฟ์ C:
- **ไม่หยุด Ollama, Ollama Model/Server, Unity, Firefox, Browser, หรือ Python ในโปรเจกต์อื่น** เพราะแอปเหล่านั้นมีวงจรชีวิตเป็นอิสระจาก VoxWeaveTTS

## ข้อควรทราบ

`Stop` เป็น **Force Stop**: งานที่กำลังสร้างเสียง/อ่านแชทจะถูกยุติโดยไม่รอให้เสร็จ เหมาะสำหรับเลิกใช้งานจริงหรือแก้กรณี Process ค้าง ไม่ควรใช้เพื่อสลับโมเดลระหว่างอ่านแชท หากทำงานปกติและหน่วยความจำเพียงพอ โมเดลที่โหลดสำเร็จจะยังค้างไว้ใน Worker เพื่ออ่านครั้งถัดไป ตามนโยบาย [Worker Gateway](ENGINE_WORKER_GATEWAY_TH.md)

ถ้าผู้ใช้ไม่มีสิทธิ์หยุด Process, หรือ Process ที่ไม่ได้มาจากโปรแกรมแต่ถูกเปิดโดยเครื่องมืออื่น จะไม่อ้างว่าหยุดได้แน่นอน Script จะแจ้ง PID หรือสถานะที่ตรวจพบให้ตรวจสอบแทน การคืนหน่วยความจำหลัง Process ถูกปิดเป็นหน้าที่ของ Windows; ไม่สามารถรับประกันว่าจะเห็น RAM Available เพิ่มขึ้นทันทีทุกเครื่อง (เช่น OS file cache อาจถูกเก็บไว้)
