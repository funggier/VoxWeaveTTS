# ตั้ง IP และพอร์ตบน Windows Portable

เปิด **VoxWeaveTTS.exe** แล้วเลือกเครือข่าย กรอก **IPv4 address** และ **Port** (1–65535) จากนั้นกด **Apply & Restart** โปรแกรมจะจดจำค่าใน `data/network.json` ภายในโฟลเดอร์ Portable

| ตัวเลือก | IP ที่โปรแกรมรับการเชื่อมต่อ | ตัวอย่าง URL |
| --- | --- | --- |
| **Local** | 127.0.0.1 ใช้จากเครื่องที่เปิดโปรแกรม | http://127.0.0.1:8765/ |
| **LAN** | เลือก IPv4 ของ Ethernet หรือ Wi-Fi ที่ต้องการ หรือกรอก IP เอง | http://192.168.1.20:8775/ |
| **Tailnet** | เลือก IPv4 ของอะแดปเตอร์ Tailscale หรือกรอก IP เอง ใช้ `tailscale ip -4` ดู IP บนเครื่องที่รันโปรแกรมได้ | http://100.84.6.5:8775/ |
| **All IPv4** | 0.0.0.0 รับการเชื่อมต่อทุกอะแดปเตอร์ IPv4 ที่เครื่องเปิดใช้งาน | ใช้ IP จริงของ LAN หรือ Tailnet ตามฝั่งที่เชื่อมต่อ |

ถ้าเข้าจากเครื่องอื่น เบราว์เซอร์จะขอชื่อผู้ใช้เริ่มต้น **voxweave** (เปลี่ยนได้จาก Launcher) และรหัสตามวิธีที่ใช้เปิดโปรแกรม ใช้พอร์ตเดียวกับที่ตั้งไว้ สำหรับ Tailnet ให้ทั้งสองเครื่องเชื่อมต่อ Tailscale และมีสิทธิ์เข้าถึง Tailscale IP กับพอร์ตนั้นตามนโยบายของ Tailnet ส่วน LAN ใช้ HTTP ภายในเครือข่ายที่เชื่อถือได้ หาก Windows Firewall บล็อก ให้เปิดเฉพาะพอร์ตและขอบเขตเครือข่ายที่ต้องการโดยไม่ทำ port forwarding สู่ Internet

การติดตั้งโมเดลและการเปลี่ยนค่าการเข้าถึงไฟล์ของ AI ทำจากเครื่องเซิร์ฟเวอร์ ปุ่ม Export / Save As (.json) บันทึกไฟล์ลงบนอุปกรณ์ที่เปิดเบราว์เซอร์ เมื่อเปิดผ่าน IP ของ LAN หรือ Tailnet ส่วนขยาย TikTok เชื่อมต่อที่ 127.0.0.1 ตามพอร์ตที่เลือก ถ้าต้องใช้ส่วนขยายกับเครื่องอื่นในเวลาเดียวกัน ให้ใช้ **All IPv4** และกำหนดขอบเขตการเข้าถึงด้วย Firewall

## เปิดจากคำสั่ง

`Start-Dev.cmd` และ `Start-Console.cmd` อ่านค่าที่บันทึกไว้ และรับ `--host` กับ `--port` หากต้องการใช้ค่าอื่นในการเปิดรอบเดียว

~~~bat
Start-Dev.cmd --host 127.0.0.1 --port 8775
Start-Console.cmd --host 100.84.6.5 --port 8775
~~~

### กำหนดรหัสผ่านสำหรับ `Start-Console.cmd`

หากยังไม่มีรหัสที่บันทึกจาก Launcher หรือต้องการใช้รหัสอื่นสำหรับการเปิดรอบนี้ ให้เปิด **Command Prompt** ในโฟลเดอร์ VoxWeaveTTS แล้วรัน

~~~bat
set "VOXWEAVETTS_NETWORK_PASSWORD=REPLACE_WITH_YOUR_OWN_PASSWORD"
Start-Console.cmd --host 100.84.6.5 --port 8775
~~~

1. แทน `REPLACE_WITH_YOUR_OWN_PASSWORD` ด้วยรหัสสุ่มของคุณ รหัสใช้ตัวอักษร ASCII ที่พิมพ์ได้ 4–128 ตัวและไม่มีช่องว่าง ตัวอักษรอังกฤษและตัวเลขพิมพ์ในคำสั่ง `set` ได้โดยตรง
2. แทน `100.84.6.5` ด้วย IPv4 ของเครื่องที่รัน VoxWeaveTTS บน Tailscale หรือ LAN และเปลี่ยน `8775` เป็นพอร์ตที่ต้องการ
3. บนอีกเครื่อง เปิด `http://IP:พอร์ต/` แล้วเข้าด้วยชื่อผู้ใช้ `voxweave` และรหัสที่กำหนด

คำสั่ง `set` มีผลในหน้าต่าง Command Prompt ที่เปิดโปรแกรม ถ้ากำหนดตัวแปรไว้ `Start-Console.cmd` จะใช้รหัสนี้ก่อนรหัสใน `data/network.json`

ถ้าเปิดผ่าน **`VoxWeaveTTS.exe`** ให้เลือกเครือข่าย กด **Apply & Restart** แล้วใช้รหัสที่โปรแกรมสร้างและแสดงในช่อง **Network login** เมื่อเปิด `Start-Console.cmd` โดยไม่ได้กำหนดตัวแปร โปรแกรมจะใช้รหัสที่บันทึกไว้จาก Launcher ได้ด้วย

### ตั้งรหัสผ่าน IP และพอร์ตไว้ใน `Start-Console.cmd`

หากต้องการดับเบิลคลิกเพื่อเปิดด้วยค่าเดิมทุกครั้ง ให้เปิด `Start-Console.cmd` ในโปรแกรมแก้ไขข้อความ แล้วใช้ตัวอย่างนี้

~~~bat
@echo off
setlocal
cd /d "%~dp0"

rem Network password for clients on other devices
set "VOXWEAVETTS_NETWORK_PASSWORD=REPLACE_WITH_YOUR_OWN_PASSWORD"

set "PYTHONPATH=%CD%\src"
set "PYTHONNOUSERSITE=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "HF_HOME=%CD%\cache\huggingface"
set "TORCH_HOME=%CD%\cache\torch"
set "XDG_CACHE_HOME=%CD%\cache"
set "TEMP=%CD%\cache\temp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"

"%CD%\runtime\python\python.exe" -m voxweavetts --host 100.84.6.5 --port 8775 %*
if errorlevel 1 pause
endlocal
~~~

- เปลี่ยน `REPLACE_WITH_YOUR_OWN_PASSWORD` เป็นรหัสสุ่มของคุณ ใช้ตัวอักษรอังกฤษและตัวเลข 4–128 ตัวได้ (แนะนำรหัสยาวกว่านี้หากใช้งานจริง) รหัสจะเก็บเป็นข้อความในไฟล์ `.cmd`
- เปลี่ยน `100.84.6.5` เป็น IPv4 ของเครื่องที่รัน VoxWeaveTTS บน Tailscale หรือ LAN และเปลี่ยน `8775` เป็นพอร์ตที่ต้องการ
- บันทึกไฟล์แล้วดับเบิลคลิก `Start-Console.cmd` บนเครื่องที่รันโปรแกรม จากนั้นเปิด `http://IP:พอร์ต/` บนเครื่องอื่น แล้วเข้าด้วยชื่อผู้ใช้ `voxweave` และรหัสที่กำหนด
