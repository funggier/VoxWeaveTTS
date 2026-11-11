# VoxWeaveTTS — โหมดการทำงานอิสระและการตั้งค่ากลาง

> v0.3.0.dev18 (Local Preview) · ระบบหลายโหมดและ OBS เดียว · YouTube Live/Discord Bot รับ Official API แบบอ่านอย่างเดียวแต่ยังไม่ได้ทดสอบบัญชีจริง (Discord Client RPC ผู้ใช้ยืนยันว่าใช้งานได้แล้ว)

## โครงสร้าง

แต่ละโหมด (รวม Discord Client สำหรับเลือก Channel ID) มีช่องข้อความ ตัวเล่นเสียง งานเสียง และ UI สำหรับงานของตนเอง โดยไม่ใช้ช่องข้อความของโหมดอื่นร่วมกัน แต่ใช้ TTS Engine, Model, Voice, Speed, Gain, Pitch, Bass, Treble, Formant Preserve, Voice Preset, Seed, Rules และ Pronunciations **ส่วนกลาง** ร่วมกัน

ค่าส่วนกลางมีผลกับงานใหม่ ไม่ย้อนเปลี่ยน WAV ที่สร้างไว้แล้ว ข้อความที่พิมพ์อยู่ใน Browser Memory ของโหมดนั้นและไม่เขียนลง Disk โดยอัตโนมัติ

## โหมดที่มี

| โหมด | เครื่องมือ | สถานะ |
|---|---|---|
| สร้างเสียง | ข้อความเฉพาะโหมด, สร้าง/ฟัง/ดาวน์โหลด WAV, Subtitle | ใช้งานได้ |
| อ่านเอกสาร | TXT/Markdown, แก้ข้อความในช่วง, เลือกบท, Bookmark, Auto-next, Subtitle | ใช้งานได้ |
| อ่านไลฟ์สด | ข้อความจำลอง Live Chat, สร้าง WAV, เล่น/หยุด, Subtitle | ทดลอง Local หรือรับ Official API เมื่อมี Credentials |
| Discord | ข้อความจำลอง Discord, สร้าง WAV, เล่น/หยุด, Subtitle, Discord Bot REST | ทดลอง Local หรือรับ Official API เมื่อมี Credentials |
| คิวและ Subtitle | ข้อความของคิว, WAV Jobs, Waveform และ Manual Alignment JSON | ใช้งานได้ |
| คำอ่านและกฎ | Rules/Pronunciations JSON, ตรวจ/แก้/เพิ่ม/นำเข้า/บันทึก/ทดลองคำอ่าน | ค่ากลาง |
| ตั้งค่ากลาง | Engine/Voice/Speed/DSP/Seed/Voice Preset และบันทึก/โหลดค่า | ค่ากลาง |

การคลิกแท็บในหน้าเว็บจะ **พักเสียงเก่าทันที** และยกเลิกการอ่านอัตโนมัติของ Document Reader โดยไม่ล้างข้อความที่กำลังแก้

## การตั้งค่ากลางที่บันทึกถาวร

1. ไปที่โหมด ตั้งค่ากลาง (หรือปุ่ม ตั้งค่ากลาง ด้านบน)
2. เลือก Engine/Voice และปรับ Speed, Gain, Pitch, Bass, Treble, Formant Preserve
3. กด บันทึก Engine และค่าปรับเสียงเป็นค่ากลาง เพื่อบันทึกลง data/settings/global-voice.json (Git Ignore)
4. ครั้งต่อไปจะโหลดค่ากลางกลับมาใช้; เมื่อเปิดหลายแท็บจะตรวจ Revision ไม่ให้เขียนทับกันโดยเงียบ ๆ
5. Seed, Voice Presets, JSON Rules และ Pronunciations ยังคงใช้ปุ่มบันทึกแบบเดิมในแต่ละส่วน แต่เป็นข้อมูลส่วนกลางของทุกโหมดเช่นกัน

ยังไม่มีการดาวน์โหลดโมเดลจากการเปลี่ยน Engine อัตโนมัติ ถ้าโมเดลที่บันทึกไม่พร้อม โปรแกรมจะเลือก Engine ที่พร้อมแทนโดยแจ้งสถานะ

## สิทธิ์เล่นเสียง: Single Active Workspace

หนึ่ง Local Server มีโหมดที่มีสิทธิ์เล่นเสียงและส่ง Subtitle ไป OBS เพียงโหมดเดียว

- เมื่อสลับแท็บ โปรแกรมจะพัก Audio Element ทั้งหมดและหยุด Auto-Next ภายใน Browser ก่อนรอ HTTP
- POST /v1/modes/activate ออก Token ใหม่สำหรับโหมดนั้น และล้าง Subtitle ของโหมดเก่าทันที
- รายงาน POST /v1/playback/event ต้องส่ง mode และ mode_token ที่เพิ่งได้รับ มิฉะนั้น HTTP 409 และไม่อัปเดต Subtitle
- Browser อื่น/แท็บอื่นจะได้รับ Event ผ่าน Local SSE /v1/modes/stream; มี BroadcastChannel และ Polling ประมาณ 1.2 วินาทีเป็นทางสำรอง
- OBS ใช้ Overlay เดิมช่องเดียวที่ /overlay (หรือระบุ mode=segment, estimated, activity, manual เพื่อเลือกรูปแบบ Subtitle) โดยแสดงเฉพาะ PlaybackState ของโหมดปัจจุบัน
- โหมดใหม่จะ **ไม่เล่นเสียงเองอัตโนมัติ** ต้องสั่ง Play ในโหมดนั้นก่อน
- ถ้ามีการสร้างเสียงด้วย CPU อยู่แล้ว การหยุดเสียง/Subtitle ไม่ได้หมายความว่า CPU Model Inference จะถูกยุติกลางคำทันที; ระบบพยายามยกเลิกงานและทิ้งผลที่มาช้าไม่ให้เล่น

Token นี้ใช้เพื่อจัดการสิทธิ์เล่นใน Local Loopback UI ไม่ใช่การยืนยันตัวตนเพื่อเปิด API สู่ LAN/Internet

## API

- GET /v1/modes/state: สถานะโหมดปัจจุบันและ Revision โดยไม่เปิดเผย Token
- POST /v1/modes/activate: JSON {"mode":"reader"} พร้อม Header X-VoxWeaveTTS-Intent: activate-mode; ตอบ mode_token และ Revision
- GET /v1/modes/stream: SSE event=workspace แจ้งการเปลี่ยนโหมด (ไม่มี Token)
- POST /v1/playback/event: เมื่อเปิด Workspace Controller แล้วต้องมี mode + mode_token ที่ตรงกับโหมดที่ Active
- GET /v1/settings/global-voice: อ่านค่ากลาง Engine/Voice/Speed/DSP ที่บันทึก
- POST /v1/settings/global-voice: JSON {engine_id,voice_id,speed,voice_controls,expected_revision} กับ Header X-VoxWeaveTTS-Intent: save-global-voice; บันทึกแบบ Atomic และป้องกัน Revision ขัดแย้ง

## Discord Client — เลือกห้องข้อความของบัญชีผู้ใช้

เพิ่ม Workspace ลำดับที่ 8 คือ **Discord Client** ต่างจาก Discord Bot Reader ตรงที่ใช้ Local Discord Desktop RPC ด้วยแอปที่ได้รับสิทธิ์และผู้ใช้ยินยอม (rpc + messages.read) โดยเลือก Channel ID ของห้องที่ต้องการติดตามหนึ่งห้อง ข้อความจากห้องอื่นไม่เข้าคิว และสามารถเปลี่ยนห้องโดยแก้ ID แล้วเชื่อมใหม่ โปรแกรมยังใช้ Engine/Voice/Rules ส่วนกลางและ Overlay เดียวกันเช่นเดิม ไม่ใช้ User Token หรือ Self-bot

ข้อจำกัด: ต้องได้รับสิทธิ์ RPC จาก Discord สำหรับแอปหรือบัญชีผู้ทดสอบก่อน; ยังไม่ได้ตรวจการเชื่อมกับบัญชีจริง ดู [Discord Client Reader](DISCORD_CLIENT_READER_TH.md)

## Live / Discord: Official Read-Only Inputs

เพิ่ม YouTube liveChatMessages.list และ Discord Bot REST Channel Messages Polling โดยผู้ใช้กรอก Credentials ชั่วคราวหรือใช้ Environment Variable ด้วยตนเอง โหมดเหล่านี้ยังรองรับการทดลองพิมพ์ข้อความโดยไม่เชื่อมบัญชี และเปิด Auto-read เป็นค่าเริ่มต้น แต่ยังต้องกดเชื่อมต่อแหล่งข้อความเอง

การใช้ Official API ต้องมีสิทธิ์และ Credentials ที่ถูกต้อง; ยังไม่ได้ยืนยันด้วยบัญชี Live/Discord จริง โหมดเหล่านี้ไม่มีการส่งข้อความกลับผู้ให้บริการ รองรับการอ่านทีละข้อความหลังตรวจกรอง และหยุด Source Worker ทันทีเมื่อเปลี่ยนโหมด อ่านรายละเอียด [คู่มือ Live Input](LIVE_INPUT_ADAPTERS_TH.md)

## สิ่งที่ยังไม่รองรับ

- การทดสอบ Official API กับบัญชีที่ได้รับอนุญาตจริง และ Low-Latency Gateway/StreamList
- Automatic Word/Syllable Forced Alignment ที่ตรวจ License ครบ
- การบันทึกข้อความ Draft ของแต่ละโหมดข้าม Browser Restart
- การตรวจสิทธิ์แบบ Login สำหรับ API ข้ามเครื่อง
- รับประกันหยุด CPU Inference ที่กำลังรันได้ทันทีเมื่อสลับโหมด

ดู [API](API.md), [Architecture](ARCHITECTURE.md), [Engine-neutral Core](ENGINE_NEUTRAL_CORE_TH.md) และ [Commercial License Policy](COMMERCIAL_LICENSE_POLICY_TH.md).