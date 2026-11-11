# Discord Client Reader — เลือกห้อง Discord ที่ต้องการอ่าน

> v0.3.0.dev14 — Discord Desktop Official Local RPC · ต้องได้รับอนุญาต · ยังไม่ได้ทดสอบกับบัญชีจริง

## ความสามารถ

Discord Client Reader เป็นแท็บแยกจาก Discord Bot และใช้ Discord Desktop ที่ผู้ใช้เข้าสู่ระบบไว้ตามปกติ โดยรับเฉพาะข้อความใหม่ในห้องที่ผู้ใช้ระบุด้วย **Channel ID** ไม่ต้องเชิญ Bot เข้า Server ที่ต้องการ

โปรแกรมใช้ Official Local RPC ตามขั้นตอน HANDSHAKE → AUTHORIZE (ขอสิทธิ์ rpc + messages.read) → OAuth Code Exchange → AUTHENTICATE → SUBSCRIBE MESSAGE_CREATE เฉพาะ Channel ID ที่เลือก

**สำคัญ:** Discord จำกัดสิทธิ์ Local RPC สำหรับแอปที่ได้รับอนุมัติหรือบัญชีที่อยู่ในรายชื่อผู้ทดสอบที่ได้รับอนุญาต และการอ่านข้อความจาก Client Channels ต้องได้รับสิทธิ์ messages.read อย่างชัดเจน

## วิธีกำหนดห้อง

1. เปิด Discord Desktop ตามปกติ
2. ไปที่ Settings → Advanced → เปิด Developer Mode
3. คลิกขวาที่ห้องข้อความที่ต้องการ → Copy Channel ID
4. เปิด VoxWeaveTTS → แท็บ Discord Client
5. วาง Channel ID ที่ช่อง **Channel ID ของห้องที่ต้องการอ่าน**
6. ระบุ Discord Application Client ID, Client Secret และ Registered OAuth Redirect URI ของแอปที่มีสิทธิ์ RPC
7. กด **เชื่อมและสมัครรับห้องนี้** และยืนยันสิทธิ์ใน Discord หาก Discord แสดงหน้าต่างอนุญาต
8. ตรวจสถานะ `subscribed` และ API `running` ก่อนทดสอบข้อความใหม่จากห้องนี้ ตัวเลือก Auto-read เปิดเป็นค่าเริ่มต้นแต่ผู้ใช้ปิดได้

**เปลี่ยนห้อง:** กรอก Channel ID ใหม่และกดเชื่อมอีกครั้ง ระบบจะหยุดการรับจากห้องเดิมและล้างคิวข้อความเก่า โดยคงค่าเปิด/ปิด Auto-read ที่ผู้ใช้เลือกไว้ และจะไม่อ่านข้อความใหม่จนกว่าจะกดเชื่อมใหม่

การระบุ Channel ID ไม่ได้ให้สิทธิ์อ่านข้อความในห้องที่คุณไม่มีสิทธิ์เข้าถึง ต้องเป็นห้องที่ Discord อนุญาตจริง

## พฤติกรรมและข้อจำกัด

- รับเฉพาะ MESSAGE_CREATE ที่ channel_id ตรงกับห้องที่เลือก ไม่อ่านข้อความจากห้องอื่น
- ไม่อ่านประวัติย้อนหลัง ไม่อ่าน Edit/Delete ไม่ดูดข้อมูลผู้ใช้อื่นโดยไม่ได้รับสิทธิ์
- ไม่ใช้ Discord User Token, Self-bot, การอ่านคุกกี้, Internal API, Scraping หรือดักจับ Network Traffic
- ข้ามข้อความจาก Bot/Webhook และกรองข้อความตาม Blacklist/ความยาว/ลิงก์
- Auto-read **เปิดเป็นค่าเริ่มต้น** แต่ไม่มีการเชื่อมต่อบัญชีจนกว่าผู้ใช้จะกดเชื่อมเอง และเลือกปิด Auto-read ได้
- ใช้ Engine, Voice, Speed/DSP, Seed, Rules และ Pronunciations ส่วนกลาง
- ใช้ OBS Overlay เดียวกับโหมดอื่น เมื่อเปลี่ยนแท็บจะหยุดการเล่นและการรับข้อความทันที
- Application Client Secret ส่งผ่าน HTTP Loopback ไปยัง Python Process เพื่อแลก OAuth Code ผ่าน Official Discord OAuth Endpoint และเก็บในหน่วยความจำชั่วคราวเท่านั้น ไม่บันทึกลง Disk หรือ GitHub
- หากแอปยังไม่ได้รับสิทธิ์ RPC จะไม่สามารถอ่านอัตโนมัติแบบไม่มี Bot ได้ ให้ใช้ Discord Bot Reader หรือข้อความทดลองระหว่างรอการอนุมัติ
- หาก Discord Desktop ปิดการเชื่อมต่อหรือการยืนยันสิทธิ์ไม่สำเร็จ ระบบจะแสดงสถานะ Error และล้างคิว Auto-read (โดยคงค่าช่องเปิด/ปิดไว้) แทนการวนเชื่อมต่อด้วย Session ที่หมดอายุแล้ว กรุณาตรวจว่า Discord Desktop เปิดอยู่ ใส่ Client Secret ใหม่ในช่องที่ถูกล้างหลังเชื่อมครั้งก่อน แล้วกดเชื่อมอีกครั้งและยืนยันสิทธิ์ใหม่
- การไม่มีข้อความเข้ามาชั่วคราวถือเป็น Idle ปกติ ไม่ใช่ Error; แต่ถ้าการอ่าน RPC Frame หยุดกลางแพ็กเก็ตจะให้เชื่อมใหม่เพื่อป้องกันการอ่านข้อมูลผิดขอบเขต

## ตรวจสอบหน้าต่างอนุญาตและ Redirect URI

ถ้าหน้าต่าง Discord แสดงชื่อแอป (เช่น Accent) ให้ตรวจว่าเป็น Discord Application ที่คุณสร้างหรือเชื่อถือเอง เพราะคำขอ `messages.read` ให้อ่านข้อความได้กว้าง ผู้ใช้ต้องกดยืนยันเฉพาะเมื่อเข้าใจสิทธิ์แล้ว

หากหน้าต่างบอกว่าจะ Redirect ไปที่ `http://127.0.0.1:8765` ให้ใช้ **URL นี้แบบตรงตัว** ในช่อง Registered OAuth Redirect URI ของ VoxWeaveTTS และใน Discord Developer Portal ไม่ใช่ `http://127.0.0.1:8765/callback` ซึ่งเป็นอีก URI หนึ่ง ค่า URI ในการแลก OAuth Code ต้องตรงกับ URI ที่ Discord ใช้ออก Code; การรับ Code ผ่าน Discord Desktop RPC ไม่จำเป็นต้องมี Web Callback Route

**OAuth2 URL Generator ไม่ใช่การเชื่อม RPC อัตโนมัติ**: ต้องกดเชื่อมจากแท็บ Discord Client ใน VoxWeaveTTS แล้วตอบหน้าต่างอนุญาตที่ Discord แสดงจากคำสั่ง RPC `AUTHORIZE`; การเปิด URL จาก Generator แยกต่างหากไม่ทำให้ Source Worker สมัครรับข้อความ

VoxWeaveTTS แสดงสถานะ opening_discord_pipe → handshake → awaiting_discord_consent → exchanging_oauth_code → authenticating → subscribing_channel → subscribed (และ API running) ก่อนเริ่มรับข้อความ หากค้างรออนุญาตให้ตรวจ Discord Desktop; หาก Error ให้ตรวจข้อความแสดงขั้นตอนที่ปลอดภัยและสิทธิ์แอป

## ผลทดสอบ

Unit Tests ตรวจ RPC Binary Framing, การขอ Scope, OAuth Mock, การสมัครรับห้องเดียว, การแยกข้อความคนละห้อง, การกรอง Bot/Webhook, Idle Timeout, Disconnect/Close, Handshake Timeout, สถานะ Error ของ SourceManager และสิทธิ์ Active Workspace โดยใช้ Fake RPC Transport พร้อม Browser Smoke Test ตรวจ Auto-read เมื่อเปลี่ยนห้อง/แหล่งข้อมูลขัดข้อง

ยังไม่ยืนยันการเชื่อมจริงกับ Discord Desktop ภายใต้แอปที่ได้รับอนุญาตของผู้ใช้

เอกสารทางการ:
- [Discord RPC](https://discord.com/developers/docs/topics/rpc)
- [OAuth2 Scopes](https://discord.com/developers/docs/topics/oauth2#shared-resources-oauth2-scopes)
- [Discord Developer Portal](https://discord.com/developers/applications)

ดู [Workspace Modes](WORKSPACE_MODES_TH.md), [Live Input Adapters](LIVE_INPUT_ADAPTERS_TH.md) และ [API](API.md).
