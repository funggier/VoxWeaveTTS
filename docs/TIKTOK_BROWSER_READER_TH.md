# TikTok LIVE (Browser) — ตัวรับคอมเมนต์ผ่าน DOM (ทดลอง)

สถานะ: **Development Preview** ใน Source Project หลัง v0.4.4 — **ยังไม่อยู่ในไฟล์ ZIP Release v0.4.4**

## โหมดที่มี

- **TikTok LIVE (Browser)** (รหัสภายใน `tiktok_browser`): กรอก `@username` หรือ URL `https://www.tiktok.com/@username/live` โปรแกรมเปิด Chrome/Edge แยกโปรไฟล์ อ่าน **ข้อความคอมเมนต์ใหม่ที่มองเห็นบนหน้า LIVE** ผ่าน Chrome DevTools Protocol (CDP) แล้วเข้าคิว TTS/OBS เดิม
- **TikTok LIVE (TikFinity)** (รหัสภายใน `tiktok`): โหมดเดิม ใช้ Local WebSocket ของ TikFinity Desktop `ws://localhost:21213/` ไม่เปลี่ยนการทำงานและการตั้งค่าเดิม
- **YouTube LIVE (Browser)** และ **YouTube LIVE (API)** คงแยกกันตามเดิม

## ข้อจำกัดและสิทธิ์

**TikTok ไม่เปิดเผย Chat-only Pop-out URL อย่างเป็นทางการ** โปรแกรมจึงเปิดหน้า `https://www.tiktok.com/@username/live` แล้ว **ปิดเสียงวิดีโอ** โดยไม่สั่งพักหรือซ่อนส่วนหลักของ LIVE เพราะอาจทำให้แชทไม่เริ่มทำงาน **หน้าเว็บยังอาจดาวน์โหลดข้อมูลวิดีโอ** หาก TikTok ปรับโครงสร้างเว็บหรือป้องกันการเข้าถึง หน้าแชทอาจไม่พร้อมและอาจต้องล็อกอินด้วยตัวเองใน Browser โปรไฟล์แยก

**ข้อกำหนดของ TikTok ห้ามการดึงข้อมูลโดยซอฟต์แวร์อัตโนมัติหากไม่ได้รับอนุมัติเป็นลายลักษณ์อักษร** ผู้ใช้ต้องตรวจสอบสิทธิ์และการอนุญาตก่อนใช้งานระบบ Browser DOM นี้: [TikTok Terms of Service](https://t.tiktok.com/legal/page/us/terms-of-service/en) (หัวข้อ 3.4) ฟีเจอร์นี้ไม่ใช่ช่องทางที่ TikTok รับรอง จึงไม่เหมาะกับการใช้งานเชิงผลิตจริงโดยไม่มีสิทธิ์ การเปิดใช้งานเป็นการเลือกของผู้ใช้ ไม่เชื่อมต่อโดยอัตโนมัติ

## วิธีทดลองจาก Source Project

1. เปิด `Start-Dev.cmd` แล้วเข้า Web UI ปัจจุบัน
2. เลือก Tab **TikTok LIVE (Browser)** กรอก `@username`, `username` หรือ `https://www.tiktok.com/@username/live`
3. ตั้งค่า Filter, ความยาวสูงสุด, อ่านอัตโนมัติ, อ่านชื่อผู้ส่งก่อนข้อความ และโมเดล/เสียงเฉพาะโหมด
4. กด **เชื่อมต่อ** แล้วดูประวัติสถานะใต้ปุ่ม: ตรวจสอบชื่อผู้ใช้ → ขอสิทธิ์ Workspace → เปิด Browser → เชื่อม CDP → รอ Chat DOM → พร้อมอ่านข้อความใหม่
5. เมื่อหน้า LIVE แสดงคอมเมนต์และมีข้อความใหม่หลังเชื่อมต่อ ระบบจะส่งเฉพาะ **คอมเมนต์ตัวอักษร** ผ่าน Filter → Queue TTS → Browser Audio → OBS Subtitle
6. กด **หยุดรับข้อความ** เพื่อยุติตัวรับและหน้าต่าง Browser ของโหมดนี้เท่านั้น โดยไม่กระทบ TikFinity, YouTube หรือ Discord

ข้อมูล Browser Profile ของ TikTok อยู่ใน `data/browser-profiles/tiktok-chat/`, แยกจาก YouTube และ Browser ส่วนตัว โค้ดไม่คัดลอกคุกกี้จากโปรไฟล์ทั่วไป ไม่ใช้ TikFinity และไม่ต้องใช้ API Key ข้อมูลโปรไฟล์จะถูกเก็บในโฟลเดอร์ `data/` ของโปรแกรม (ไม่ Commit)

DOM ตัวอย่างที่รองรับคือกล่อง `DivChatMessageList` หรือโครงสร้างใหม่ `[data-e2e="live-chat-container"]` โดยมีช่องแชท `[data-e2e="room-chat-input-field"]` และคอมเมนต์ `data-e2e="chat-message"` / `SpanChatMessageText` พร้อมชื่อผู้ส่ง โปรแกรมจะ **ไม่ส่งแชท ไม่กดไลก์ ไม่อ่านของขวัญ/การเข้าห้อง/กิจกรรมอื่น ๆ** ไม่อ่านข้อความที่อยู่ในหน้าจอตั้งแต่ก่อนเริ่มเชื่อม และใช้ ID จาก DOM เพื่อกันซ้ำระหว่างการตรวจเป็นช่วง ๆ

## เมื่อ Browser ของโปรแกรมแสดง "Comments off"

หากไลฟ์เดียวกันมีคอมเมนต์ใน TikTok ปกติ แต่หน้าต่างที่ VoxWeaveTTS เปิดแสดง **Comments off** อย่าเพิ่งสรุปว่าเจ้าของไลฟ์ปิดคอมเมนต์

ตรวจจากหน้าต่างจริงวันที่ 13 พฤศจิกายน 2026 พบปุ่ม **Log in** และช่องพิมพ์ `data-e2e="room-chat-input-field"` ที่มี `placeholder="Comments off"` และ `disabled` ในโปรไฟล์แยกของโปรแกรม สถานะนี้เกิดเฉพาะเซสชันที่ตรวจ ไม่ได้พิสูจน์ว่า LIVE ปิดคอมเมนต์สำหรับทุกคน

ให้เปิดหน้าต่าง TikTok ที่ VoxWeaveTTS สร้างขึ้น กด **Log in** และเข้าสู่ระบบด้วยตนเองตามขั้นตอนของ TikTok จากนั้นรีเฟรชหน้า LIVE แล้วตรวจอีกครั้ง การเข้าสู่ระบบใน Firefox/Chrome โปรไฟล์หลักไม่เท่ากับโปรไฟล์แยกของโปรแกรม

ระบบจะแยก **Comments off + Log in**, **Comments off เฉพาะ Browser นี้**, และ **รอ DOM แชท** และจะตรวจซ้ำเป็นระยะโดยไม่สรุปว่าผู้จัดไลฟ์เป็นผู้ปิด ไม่ดัดแปลงสิทธิ์ TikTok และไม่คัดลอกคุกกี้หรือรหัสผ่านจาก Browser อื่น

## สถานะการทดสอบ

- ทดสอบ URL/Username Validation, ความปลอดภัยของ Target, การกรองข้อความเดิม, การเชื่อมต่อ Source Worker และการไม่อ่านข้อความเก่า
- ทดสอบ Chrome CDP กับ **หน้า HTML จำลอง TikTok Chat** โดยตรวจว่าอ่านข้อความคอมเมนต์ แต่ไม่อ่าน Gift Row ผ่าน `python tests/tiktok_browser_dom_integration_smoke.py`
- ทดสอบหน้า UI จริงผ่าน local server ด้วย `python tests/browser_ui_click_smoke.py` และ Smoke Test `node tests/tiktok_browser_ui_smoke.cjs`
- **ยังไม่ได้ทดสอบกับ LIVE ของ TikTok จริง** และ DOM selectors อาจเปลี่ยนได้ ไม่มีการรับรองว่าจะใช้งานได้กับ LIVE ทุกห้อง โปรดใช้ TikFinity เดิมหากต้องการแหล่งข้อความที่ผ่านการทดสอบกับแอปในเครื่องแล้ว
