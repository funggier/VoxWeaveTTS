# YouTube LIVE (Browser) — Chat-only DOM Reader (ทดลอง)

สถานะ: **โหมดทดลองรวมใน Release v0.7.1** และเพิ่ม Live chat อัตโนมัติกับมาตรการลด Background Throttling แล้ว (ยังไม่ได้รับประกันเมื่อ YouTube หยุดอัปเดตจริง)

## การทำงาน

เพิ่ม Tab สองโหมดแยกกัน:

- **YouTube LIVE (Browser)**: เปิดหน้าต่าง Chrome หรือ Edge แบบ Chat-only และอ่านข้อความใหม่จาก DOM ผ่าน Chrome DevTools Protocol (CDP) บนเครื่องเดียวกัน ไม่ต้องใช้ YouTube Data API Key และ **ไม่ใช้โควตาของ YouTube Data API**
- **YouTube LIVE (API)**: โหมดเดิม (รหัสภายใน `live`) ใช้ YouTube Data API, `streamList` หรือ REST เดิม ไม่แก้ไขค่าตั้งเก่า

ระบบ Browser เป็นโหมดทดลองที่ไม่ใช่ช่องทางรับข้อมูลอย่างเป็นทางการของ YouTube การอ่าน DOM ต้องตรวจสอบว่าได้รับอนุญาตตามข้อกำหนดของ YouTube ก่อนใช้จริง: https://www.youtube.com/t/terms (ส่วน automated access) และ https://developers.google.com/youtube/terms/developer-policies (ส่วน scraping)

## วิธีทดลอง

1. เปิดโปรเจกต์จาก `Start-Dev.cmd` (Chrome หรือ Edge ต้องติดตั้งอยู่ในเครื่อง)
2. เปิด Tab **YouTube LIVE (Browser)** และกรอก YouTube Video ID 11 ตัว หรือ URL เช่น `https://www.youtube.com/watch?v=VIDEO_ID`
3. ตั้งค่ากรองข้อความ ความยาวสูงสุด อ่านอัตโนมัติ และอ่านชื่อผู้ส่ง ตามต้องการ
4. กด **เชื่อมต่อ** — โปรแกรมจะเปิดหน้าต่างใหม่เฉพาะ `https://www.youtube.com/live_chat?is_popout=1&v=VIDEO_ID` ไม่เปิดหน้าวิดีโอ; ตั้งแต่ v0.7.1 โปรแกรมจะพยายามเลือก **Live chat** แทน **Top chat** อัตโนมัติเมื่อพบเมนู
5. เมื่อ Browser แสดง Chat ให้เปิดหน้าต่างนั้นไว้ (สามารถสลับไปทำงานหน้าต่างอื่นได้) โปรแกรมจะเก็บเฉพาะข้อความประเภท text chat ที่มาหลังครั้งแรกที่เห็น DOM; **ไม่อ่านประวัติก่อนหน้า** เพื่อหลีกเลี่ยงการอ่านข้อความย้อนหลังซ้ำ หากตรวจพบ Top chat ระบบจะพยายามเปลี่ยนเป็น Live chat ก่อนเริ่ม baseline สูงสุดประมาณ 12 วินาที; หากยืนยันไม่ได้ จะยังอ่านต่อพร้อมแสดงคำเตือน ไม่ค้างเชื่อมต่อตลอดไป
6. ข้อความใหม่จะเข้าคิวเดิม ผ่านตัวกรองคำ/URL/สแปมและสร้างเสียงด้วย Engine/Voice ของ Tab นี้; เมื่อ Browser เล่น WAV จะใช้ OBS Subtitle เดิม
7. กด **หยุดรับข้อความ** เพื่อหยุด Source Worker และปิดหน้าต่าง Browser ที่โปรแกรมเปิดไว้

การสลับ Tab ไม่หยุด Browser หรือการอ่านโดยอัตโนมัติ แต่การปิดโปรแกรมหรือการยึดสิทธิ์โหมดจาก Browser อีกแท็บจะปิด Source Worker ของโหมดนั้นตามปกติ

### สถานะระหว่างเชื่อมต่อ

ใต้ปุ่ม **เชื่อมต่อ** จะมีสถานะปัจจุบันและประวัติขั้นตอนการเชื่อมต่อ (เก็บสูงสุด 12 ขั้นตอนล่าสุด):

1. ตรวจสอบ URL/Video ID และตัวกรอง
2. ขอสิทธิ์ Workspace และส่งคำสั่งเริ่มตัวรับข้อความ
3. ค้นหา/เปิด Chrome หรือ Edge ในหน้าต่าง Chat-only และรอพอร์ตควบคุมเฉพาะเครื่อง
4. ค้นหาหน้า YouTube Live Chat แล้วเชื่อมต่อ Chrome DevTools Protocol
5. รอ DOM ของ Live Chat พร้อมและพยายามเลือก **Live chat** อัตโนมัติ (Top chat อาจกรองข้อความ) ก่อนเริ่มรับเฉพาะข้อความใหม่

หากหน้า Chat ยังไม่พร้อม จะแสดงคำแนะนำให้ตรวจสอบการเปิดแชทและการโหลดหน้าเว็บ หากเชื่อมต่อไม่สำเร็จ จะแสดงสาเหตุที่ Backend รายงานและช่วงเวลาก่อนลองใหม่ (เมื่อเกี่ยวข้อง)

สามารถทดสอบปุ่มจากหน้าเว็บจริงกับ URL ผิด โดยไม่ต้องเชื่อม YouTube ได้ด้วย `python tests/browser_ui_click_smoke.py` (ต้องเปิด `Start-Dev.cmd` ก่อน)

## รายละเอียดเทคนิคและความปลอดภัย

- Backend `src/voxweavetts/youtube_browser.py` ใช้ Python Standard Library สำหรับ CDP WebSocket และอ่าน DOM; ไม่มี dependency Browser Automation เพิ่ม
- เปิด Chrome ก่อน หากไม่มีจึงใช้ Edge, โดยใช้ `--remote-debugging-port=0` (พอร์ตสุ่ม), `--remote-debugging-address=127.0.0.1` และหน้าแชทผ่าน HTTPS เท่านั้น
- ใน v0.7.1 เพิ่ม Chromium flags `--disable-background-timer-throttling`, `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding` และ `--disable-features=CalculateNativeWinOcclusion` **เฉพาะหน้าต่าง Chrome/Edge ที่โปรแกรมเปิดเอง** พร้อม CDP Focus Emulation และการตั้ง Page Lifecycle เป็น Active เพื่อช่วยลดปัญหาหน้าต่างถูกบัง/ไม่อยู่ในโฟกัส ไม่ย้ายหน้าต่างขึ้นหน้า ไม่แก้การตั้งค่า Firefox/Chrome ส่วนตัว
- สถานะ YouTube Browser แสดง **Top chat / Live chat / กำลังเปลี่ยน / ยืนยันไม่ได้** และสถานะการมองเห็นหน้า หากยังเป็น Top chat อาจทำให้ไม่ได้รับข้อความทั้งหมด
- แยก Browser Profile ใน `data/browser-profiles/youtube-chat/` (ไฟล์นี้อยู่ใน .gitignore) ไม่ใช่ Browser Profile Firefox/Chrome ส่วนตัว ไม่คัดลอกคุกกี้หรือรหัสผ่าน
- ไม่ส่ง API Key, Account Token หรือ Cookie เข้า Source API; ไม่ใส่ CDP endpoint ใน API Status/Logs
- อ่าน DOM ของ `yt-live-chat-text-message-renderer` เฉพาะ `#author-name` และ `#message`, ใช้ Message ID กันซ้ำ โดยใช้ ID ชั่วคราวต่อ DOM node หากไม่มี ID จริง
- ถ้าหน้า YouTube ไม่มี Live Chat, ต้องล็อกอิน, เปลี่ยนโครงสร้าง DOM หรือเกิด Rate Limit โปรแกรมไม่รับรองว่าจะอ่านได้ จะแสดงสถานะข้อผิดพลาด/รอเชื่อมต่อ ไม่พยายามข้าม Captcha หรือการป้องกันของ YouTube
- ไม่เปิดวิดีโอ ไม่ส่งข้อความกลับไปยัง YouTube และไม่ใช่ official Data API
- หากต้องการความเสถียร/การรองรับอย่างเป็นทางการ ให้เลือก Tab **YouTube LIVE (API)**

## สถานะการทดสอบ

- ทดสอบ Parser Video ID, การไม่อ่านข้อความเก่า, การกันข้อความซ้ำ, การเริ่ม/หยุด Worker และความเป็นอิสระของโหมดผ่าน Unit Tests
- ทดสอบจริงกับ Chrome ในโปรไฟล์แยก โดยเปิดหน้า HTML จำลองแชทและอ่าน DOM ผ่าน CDP (เรียก `python tests/browser_dom_integration_smoke.py`) — ผ่าน
- ทดสอบจริงกับ Chrome ที่ติดตั้งในเครื่องอีกครั้งโดยใช้ **DOM จำลอง Top chat และ Live chat** ยืนยันว่าเปลี่ยน Top → Live ได้ผ่าน CDP และคำสั่ง Focus/Lifecycle ได้รับการยอมรับจาก Chrome
- **ยังไม่ได้ทดสอบปัญหาการไม่อัปเดตกับ YouTube LIVE จริงขณะย่อ/ซ่อนหน้าต่างเป็นเวลานาน** เนื่องจากต้องมีไลฟ์ที่เข้าถึงได้และการอนุญาตที่เหมาะสม จึงไม่รับรองว่าจะไม่มีการหยุดเมื่อ YouTube เองไม่ส่งข้อมูลหรือ Chromium ระงับเพจในบางสถานการณ์ หากต้องการความเสถียรของข้อมูลให้ใช้ YouTube LIVE (API)
- **การแก้ Top chat และ Background Throttling รวมใน Windows Portable Release v0.7.1** แต่ยังต้องทดลองบน YouTube LIVE จริงเป็นเวลานานเพื่อยืนยันความเสถียร
