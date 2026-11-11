# Live / Discord Official Input Adapters — VoxWeaveTTS

สถานะ: v0.3.0.dev18 Local Preview — YouTube Live และ Discord Bot ยังไม่ได้ทดสอบด้วยบัญชีจริง; ผู้ใช้ยืนยันว่า Discord Client RPC รับข้อความจริงได้ใน dev17

## หลักการ

โหมดอ่านไลฟ์สดและ Discord เลือกได้ระหว่างการพิมพ์ข้อความเองหรือเชื่อมต่อ Official API เพื่อรับข้อความใหม่ แต่ละโหมดเก็บข้อความและเสียงแยกกัน ขณะที่ Engine/Model, Voice, Speed/DSP, Seed, Preset และ Rules/Pronunciations ยังคงเป็นค่ากลาง

ผู้ใช้ต้องคลิกเชื่อมต่อเองทุกครั้ง ไม่มีการติดต่อ Social API อัตโนมัติเมื่อเปิดโปรแกรม Credentials ที่กรอกจะถูกล้างออกจากช่อง Input หลังเชื่อมต่อสำเร็จและเก็บในหน่วยความจำของ Python Source Worker เท่านั้น ไม่บันทึกลงดิสก์หรือ GitHub

## วิธีเชื่อม YouTube Live

1. เตรียม YouTube Data API v3 API Key ที่เปิดสิทธิ์แล้วจาก Google Cloud Project ของผู้ใช้เอง แนะนำจำกัดการใช้ Key ให้เหมาะกับโปรแกรม
2. เปิดโหมด อ่านไลฟ์สด แล้วระบุ Video ID (11 ตัว) ของ Live ที่กำลังดำเนินอยู่ หรือระบุ liveChatId โดยตรง
3. กรอก API Key ในช่องชั่วคราว หรือกำหนด Environment Variable ชื่อ VOXWEAVE_YOUTUBE_API_KEY ให้โปรเซสที่เปิดโปรแกรม
4. เลือก Blacklist ของคำที่ไม่ต้องการและความยาวสูงสุด ก่อนกด เชื่อมต่อ API
5. ระบบใช้ liveChatMessages.list; หน้าแรกตั้งเป็นจุดเริ่มต้นและไม่อ่านข้อความประวัติก่อนเชื่อมต่อ จากนั้นใช้ nextPageToken และ pollingIntervalMillis ของ API ในคำขอต่อไป

ข้อจำกัด: ใช้ REST Polling (อย่างน้อยประมาณ 5 วินาทีขึ้นไป) ไม่ใช่ streamList และมีค่าโควต้าการเรียก API ผู้ใช้ควรตรวจสิทธิ์และโควต้าของโครงการตัวเอง

เอกสาร: https://developers.google.com/youtube/data/live/docs/liveChatMessages/list

## วิธีเชื่อม Discord

1. สร้างหรือใช้ Discord Bot Application ที่คุณมีสิทธิ์จัดการ เชิญบอตเข้า Channel โดยให้สิทธิ์ View Channel และ Read Message History
2. ตรวจ MESSAGE_CONTENT Privileged Intent หากต้องอ่านข้อความทั่วไปภายใน Guild; Discord อาจส่งเนื้อหาว่างหาก Bot ไม่ได้รับสิทธิ์นี้
3. เปิด Discord Developer Mode แล้วคัดลอก Channel ID ที่ต้องการ
4. เปิดโหมด Discord ใส่ Channel ID และ Bot Token (ไม่ใช่ User Token) หรือกำหนด Environment Variable ชื่อ VOXWEAVE_DISCORD_BOT_TOKEN ก่อนเปิดโปรแกรม
5. กดเชื่อมต่อ ระบบจะอ่านผ่าน Discord Official REST API แบบ Read-only ทุกอย่างใช้ Bot Token ที่ได้รับอนุญาต และใช้ after Snowflake ID เพื่อดึงเฉพาะข้อความใหม่

Discord Reader ใช้ Polling ขั้นต่ำ 5 วินาที และเคารพ Retry-After / X-RateLimit-Reset-After เมื่อถึงข้อจำกัด API ไม่ใช่ Gateway WebSocket และยังไม่รองรับการเปลี่ยนแปลง Edit/Delete หรือข้อความจาก Channel อื่นอัตโนมัติ

เอกสาร:
- https://discord.com/developers/docs/resources/message#get-channel-messages
- https://discord.com/developers/docs/topics/rate-limits
- https://support-dev.discord.com/hc/en-us/articles/6207308062871-What-are-Privileged-Intents

## ตัวเลือกอ่านและกรองข้อความ

ค่าเริ่มต้น **อ่านข้อความใหม่อัตโนมัติ = เปิด** แต่จะไม่เชื่อมต่อหรือเริ่มอ่านข้อความจนกว่าผู้ใช้จะกดเชื่อมต่อเอง สามารถปิดตัวเลือกได้ หากปิด ข้อความใหม่จะปรากฏในรายการและสามารถกด เลือกข้อความนี้ เพื่อใส่ช่องข้อความเฉพาะโหมด แล้วกดสร้างเสียง/ฟังด้วยตนเอง

เมื่อเปิดอัตโนมัติ โปรแกรมอ่านทีละข้อความ ไม่แทรกกลาง WAV ที่กำลังเล่น พร้อมเก็บ Source Message ID เพื่อลดการสร้างงานซ้ำ และรอการเล่นสิ้นสุดก่อนอ่านข้อความถัดไป

- Backend Pending Queue สูงสุด 40 ข้อความ, Browser Auto-read รอได้สูงสุด 12 ข้อความ (ไม่รวมข้อความที่กำลังสร้างเสียง/เล่นเสียง) คิวเต็มแล้วข้ามข้อความ **ใหม่** โดยไม่ทิ้งข้อความเก่าที่ยังรอ พร้อมตัวนับที่หน้าจอ
- ข้อความที่เล่นเสียงจบจริงจึงถูกนับว่าอ่านแล้ว ประวัติอ่านแล้วเริ่มต้นเก็บ 20 รายการ ปรับได้ 0–100 โดยลบจากเก่าสุดเมื่อเกินจำนวน ไม่แตะข้อความที่กำลังรออ่าน; ข้อความที่เลือกเอง/ถูกข้ามเก็บสูงสุด 25 รายการใน Browser
- ข้อความยาวเกินเพดาน (ค่าเริ่มต้น 240 ตัวอักษร, กำหนดได้ 20–280), ลิงก์ URL, คำสั่งที่เริ่มด้วย ! หรือ /, @everyone/@here และคำที่ผู้ใช้ Block ไว้จะไม่ถูกส่งไปอ่าน
- Discord Bot/Webhook Messages ถูกข้ามโดยค่าเริ่มต้น เพื่อไม่ให้เกิดการอ่านวนจากบอต
- เมื่อเปลี่ยนโหมด จะหยุดการรับข้อความและ Audio/Auto-read ทันที พร้อมรีเซ็ต Overlay โดยคงค่าช่อง Auto-read และไม่รับข้อความอีกจนกว่าจะกดเชื่อมต่อใหม่
- ไม่มีการส่งข้อความกลับไปหา Chat, ลบข้อความ หรือดำเนินการด้วยสิทธิ์บัญชีบนแพลตฟอร์ม
- Token ที่ส่งไป Backend ไม่อยู่ใน API Status, Speech Job หรือ Subtitle Payload และ URL ปลายทางถูกจำกัดเฉพาะ Official Host

## Export / Import การตั้งค่ารายช่องทาง (v0.3.0.dev18)

1. เลือกแท็บ YouTube Live, Discord Bot หรือ Discord Client แล้วกรอกเฉพาะช่องที่ต้องการ (ช่องที่ยังไม่ทราบ **เว้นว่างได้** รวมถึงช่องตัวเลข)
2. กด **Export การตั้งค่า (.json)** เพื่อดาวน์โหลดไฟล์ JSON ของช่องทางนั้น **ทุกค่าที่กรอก** รวมถึง API Key, Bot Token, Client Secret
3. ต่อมาเลือกช่องทางเดียวกันแล้วกด **Import การตั้งค่า (.json)** เลือกไฟล์กลับมา โปรแกรมจะกรอกข้อมูลให้ทุกช่องและคงช่องที่เว้นว่างไว้
4. เติมส่วนที่ขาดด้วยตนเองแล้วกด **เชื่อมต่อ** เมื่อพร้อม Import ไม่เชื่อมต่อ API หรือเริ่มอ่านเอง ถ้ากำลังเชื่อมต่อกับแหล่งเดิม Import จะหยุดแหล่งเดิมก่อนเพื่อไม่ให้ตั้งค่าในจอผิดกับการเชื่อมต่อเดิม

ไฟล์แยกตาม `mode` และมี `format` / `version` ใช้ตรวจความเข้ากันได้และกันการ Import ข้ามโหมด ข้อมูลลับในไฟล์เป็น **Plaintext ไม่เข้ารหัส** ผู้ใช้เป็นผู้ดูแลไฟล์ โปรดเก็บในพื้นที่ปลอดภัย อย่าอัปโหลด GitHub, คลาวด์ที่แชร์ หรือโพสต์ในแชตเมื่อไม่ตั้งใจเผยรหัสผ่าน เนื่องจากหน้าเว็บล้างช่อง Credential หลัง Connect สำเร็จ ควร Export ก่อนกด Connect หากต้องการให้ไฟล์เก็บ Secret ครบถ้วน การ Export/Import เป็นการทำงานเฉพาะใน Browser ไม่มีการอัปโหลดไฟล์ไป Backend และไม่บันทึกไฟล์ใดในโปรเจกต์โดยอัตโนมัติ

## Local API

| Endpoint | ใช้งาน |
|---|---|
| POST /v1/sources/start | เปิด Source ด้วย mode, mode_token, source_id, credential, filters |
| GET /v1/sources/status?mode=live | ดูสถานะโดยไม่คืน Credential หรือ Token |
| POST /v1/sources/drain | ดึงข้อความใหม่ทีละ 1–20 รายการ โดยตรวจ Active Mode Token |
| POST /v1/sources/stop | หยุด Source และล้าง Queue |

การทำ POST ใช้ Content-Type application/json และ X-VoxWeaveTTS-Intent เป็น start-live-source / drain-live-source / stop-live-source ให้ตรง Endpoint และต้องได้รับ mode_token จาก POST /v1/modes/activate ก่อน

ห้ามใส่ Credential ตัวจริงลงไฟล์ทดสอบหรือ Git สามารถใช้ช่อง Input หรือ Environment Variable ในเครื่องแทน

## ข้อจำกัดและงานถัดไป

ยังไม่ได้ยืนยันด้วยบัญชี Live/Discord จริง, ไม่มี Gateway/WebSocket ที่ส่งข้อความแบบ Latency ต่ำ, ยังไม่มี Moderation ขั้นสูง, ไม่มี Multi-Channel พร้อมกันและไม่มี Queue ข้ามการปิด Server โมเดล TTS ยังคงเป็น CPU Engine ที่ใช้เดิม

ดู [Workspace Modes](WORKSPACE_MODES_TH.md), [API](API.md) และ [Commercial License Policy](COMMERCIAL_LICENSE_POLICY_TH.md).
