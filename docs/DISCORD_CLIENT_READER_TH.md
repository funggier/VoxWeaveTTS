# Discord Client Reader — เลือกห้อง Discord ที่ต้องการอ่าน

> v0.3.0.dev18 — Discord Desktop Official Local RPC · ต้องได้รับอนุญาต · ผู้ใช้ยืนยันว่าใช้งานกับบัญชีจริงสำเร็จใน dev17

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

## ตรวจสอบ OAuth หลังหน้าต่าง Discord ยืนยันแล้ว

หากสถานะเดิมขึ้น `Discord RPC OAuth denied` แปลว่าได้ Authorization Code แต่แลก Access Token ไม่สำเร็จ จึงยังไม่เกี่ยวกับ Channel ID หรือ Auto-read รุ่น dev16 จะส่ง `client_id` และ `scopes` ใน RPC `AUTHORIZE` ตามเอกสาร Discord โดย **ไม่มี** `redirect_uri` ในคำสั่ง RPC (ไม่อยู่ในโครงสร้าง Argument ทางการ) และยังส่ง Redirect URI ที่ผู้ใช้ตั้งไว้ในคำขอ `/api/oauth2/token` และจะแสดงรหัสผิดพลาดแบบจำกัดรายการโดยไม่เปิดเผยข้อความตอบกลับดิบ

- `invalid_client`: ตรวจว่าใส่ **Client Secret** ของ Discord Application เดียวกับ Client ID ไม่ใช่ Public Key หรือ Bot Token และหากเคย Reset Secret ให้ใช้ค่าล่าสุด
- `invalid_grant`: กดเชื่อมใหม่เพื่อขอ Code ใหม่ ตรวจ Redirect URI ใน Developer Portal และโปรแกรมให้ตรงกันทุกอักขระ รวมถึงพอร์ตและเส้นทาง (`http://127.0.0.1:8765` ไม่เท่ากับ `http://127.0.0.1:8765/callback`)
- `unauthorized_client`: ตรวจสิทธิ์ RPC / ข้อจำกัดของแอปหรือบัญชีผู้ทดสอบกับ Discord
- `invalid_request`: ตรวจ Redirect URI และรูปแบบคำขอ
- กรณี HTTP/Network อื่น: ดูรหัสสถานะที่ปลอดภัย; ไม่ต้องส่ง Client Secret, Authorization Code หรือ Access Token เพื่อให้วินิจฉัย

การเลือก `rpc` / `messages.read` ใน OAuth2 URL Generator ไม่ได้ยืนยันว่าแอปมีสิทธิ์ RPC และการเปิด URL Generator โดยตรงไม่ทำให้ Local RPC Session เชื่อมต่อสำเร็จ ต้องเริ่มจากปุ่มเชื่อมใน VoxWeaveTTS ผู้ใช้ต้องยืนยันหน้าต่าง Discord ด้วยตนเอง

## เมื่อ RPC AUTHORIZE ตอบรหัส 5000

Discord RPC Error 5000 หมายถึง OAuth2 Error และรายละเอียดจะอยู่ในฟิลด์ message ของ Error Response ซึ่งรุ่น dev16 จะแสดง **เฉพาะรหัส OAuth ในรายการที่อนุญาต** เช่น `invalid_scope`, `invalid_request` ไม่ส่งข้อความตอบกลับดิบไปหน้าเว็บ

หากพบ `invalid_scope` ให้ตรวจว่า Discord Application ได้รับอนุมัติให้ใช้ Local RPC หรือบัญชีที่ทดสอบอยู่ใน **รายชื่อ Authorized Testers** ของแอป โดยการเห็น `rpc` และ `messages.read` ใน OAuth2 URL Generator ไม่ได้ยืนยันสิทธิ์ใช้งาน Local RPC การกรอก Redirect URI ซ้ำหรือสลับ `/callback` จะไม่แก้ปัญหาสิทธิ์ Scope

โปรดอย่าส่ง Client Secret, Authorization Code หรือ Access Token ให้ผู้อื่น หาก API แสดงเพียง "OAuth2 error (5000); details unavailable" ยังสรุปไม่ได้ว่าเป็น invalid_scope หรือสาเหตุอื่น และต้องตรวจการอนุมัติจาก Discord

อ้างอิง: [Discord RPC](https://discord.com/developers/docs/topics/rpc), [Discord Error Codes](https://discord.com/developers/docs/topics/opcodes-and-status-codes#rpc-rpc-error-codes)

## เมื่อได้ HTTP 403 ในขั้นตอน OAuth Token Exchange

Discord กำหนดให้ HTTP API Client ส่ง User-Agent ที่ระบุแอปและเวอร์ชันอย่างชัดเจน หากใช้ User-Agent ค่าเริ่มต้นของ `urllib` อาจถูกบล็อกได้ (ดู [Discord HTTP API — User Agent](https://discord.com/developers/docs/reference#user-agent)). ใน dev17 โปรแกรมส่ง `VoxWeaveTTS (https://github.com/funggier/VoxWeaveTTS, 0.3.0.dev17)` และใช้ `https://discord.com/api/v10/oauth2/token` ตามเอกสาร

จากเครื่อง Windows ของผู้ใช้ การส่งคำขอทดสอบด้วยข้อมูล **ปลอมเท่านั้น** ให้ผล HTTP 403 สำหรับ User-Agent เดิม แต่ User-Agent ใหม่ได้ HTTP 400 `invalid_client` ตามคาด จึงยืนยันว่าปัญหา User-Agent เป็นหนึ่งในสาเหตุที่ทำให้ไม่ผ่าน Token API ได้ ไม่จำเป็นต้องเปลี่ยน Redirect URI หรือ Channel ID เพื่อแก้ HTTP 403 ชนิดนี้

ให้รีโหลดเว็บและกดเชื่อมใหม่ด้วย Client Secret ปัจจุบันเพื่อขอ Code ใหม่จาก Discord Desktop อีกรอบ ถ้ายังค้างให้ส่งเฉพาะข้อความ API Error ที่ไม่รวมข้อมูลลับ โดยยังไม่รับรองว่า Discord อนุญาตให้แอปรับ `messages.read` จากห้องจริงแล้ว

## คิวเสียงและโปรไฟล์ตั้งค่าช่องทาง (dev18)

คิวอ่านข้อความ Discord Client ใช้แกนร่วมกับ YouTube Live และ Discord Bot แต่แต่ละโหมดมีคิวและการเล่นเสียงอิสระ อ่านทีละข้อความตามลำดับ เมื่อข้อความใหม่ล้นคิว 12 รายการจะข้ามเฉพาะข้อความใหม่ไม่ลบข้อความเก่าที่ยังรอ ประวัติที่อ่านเสร็จเก็บได้ 0–100 ข้อความ (ค่าเริ่มต้น 20) และลบจากเก่าสุดเท่านั้น

กด Export (.json) ในแผง Discord Client เพื่อเก็บ **ทุกช่อง** รวม Client ID, Redirect URI, Client Secret, ตัวกรองและประวัติ ช่องที่ยังไม่ได้กรอกสามารถเว้นว่างได้ เมื่อ Import กลับข้อมูลจะเติมในช่องเดิมโดยไม่เชื่อมต่อเอง โปรด Export ก่อน Connect หากต้องการเก็บ Client Secret เพราะหลังเชื่อมสำเร็จโปรแกรมจะล้างช่อง Secret ไฟล์ JSON เป็น **ข้อความธรรมดาที่ไม่เข้ารหัส** ห้ามเผยแพร่เป็นสาธารณะ

## ผลทดสอบ

Unit Tests ตรวจ RPC Binary Framing, การขอ Scope, OAuth Mock, การสมัครรับห้องเดียว, การแยกข้อความคนละห้อง, การกรอง Bot/Webhook, Idle Timeout, Disconnect/Close, Handshake Timeout, สถานะ Error ของ SourceManager และสิทธิ์ Active Workspace โดยใช้ Fake RPC Transport พร้อม Browser Smoke Test ตรวจ Auto-read เมื่อเปลี่ยนห้อง/แหล่งข้อมูลขัดข้อง

ยังไม่ยืนยันการเชื่อมจริงกับ Discord Desktop ภายใต้แอปที่ได้รับอนุญาตของผู้ใช้

เอกสารทางการ:
- [Discord RPC](https://discord.com/developers/docs/topics/rpc)
- [OAuth2 Scopes](https://discord.com/developers/docs/topics/oauth2#shared-resources-oauth2-scopes)
- [Discord Developer Portal](https://discord.com/developers/applications)

ดู [Workspace Modes](WORKSPACE_MODES_TH.md), [Live Input Adapters](LIVE_INPUT_ADAPTERS_TH.md) และ [API](API.md).
