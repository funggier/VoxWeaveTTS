# Waveform Editor — VoxWeaveTTS (v0.3.0.dev8)

> สถานะ: Engine-neutral Manual Alignment Tool · ใช้ WAV จริงใน Browser · **ไม่ใช่ Forced Alignment อัตโนมัติ**

## เป้าหมาย

ช่วยกำหนดเวลาเริ่มและจบของคำ/วลีสำหรับ Subtitle ที่ผู้ใช้ฟังตรวจเอง โดยแสดงคลื่นเสียงจาก WAV ในหน้า Manual Alignment. ไม่ติดตั้งโมเดลหรือ JavaScript Library ภายนอกและไม่มีการอัปโหลด WAV ขึ้น Cloud

Waveform Editor โหลด WAV ที่สร้างเสร็จแล้วจาก Local Speech Queue (GET /v1/jobs/{speech_id}/audio) เข้าหน่วยความจำ Browser แล้ววิเคราะห์ Peak Amplitude ของ PCM16. โค้ดอ่าน RIFF/WAVE, PCM16 Mono/Stereo 8–96 kHz โดยตรง; ถ้า Engine ส่ง WAV Format อื่น ผู้ใช้ยังแก้เวลา Manual Cues ผ่านช่องตัวเลขได้ตามเดิม แต่ Waveform จะไม่แสดง

## วิธีใช้

1. เปิด http://127.0.0.1:8765/ และกด Ctrl+F5. สร้างเสียงจาก Speech Queue ก่อน
2. กางแผง **Manual Alignment** แล้วกด **โหลดงานล่าสุดที่ Ready**
3. Waveform จะปรากฏพร้อมช่วง Speech/Silence และ Cue ที่มีอยู่ (ถ้ามี)
4. ใช้ **ซูม 1–32×** และ Slider **เลื่อนตำแหน่งที่แสดง** เพื่อดูช่วงสั้นที่ต้องการ
5. คลิกบน Waveform เพื่อเลื่อน Audio Player ไปยังจุดที่ต้องการ และกด Play เพื่อฟัง
6. คลิกแล้วลากบน Waveform เพื่อกำหนดเวลาเริ่ม–จบ; ค่าสองช่อง Milliseconds จะเปลี่ยนตามช่วงที่เลือก หรือจะจับเวลาจาก Playhead ผ่านปุ่มเดิมก็ได้
7. ไฮไลต์ข้อความที่ได้ยินจริงในช่อง Speech Segment แล้วกด **เพิ่ม Cue จากข้อความที่ไฮไลต์**
8. ตรวจ JSON และกด **ใช้เวลา Subtitle ในงานนี้** ขณะพักเสียง จากนั้นเริ่ม Play ใหม่และเปิด OBS Overlay ที่ http://127.0.0.1:8765/overlay?mode=manual

Keyboard: เมื่อ Focus อยู่บน Waveform ให้กดลูกศรซ้าย/ขวาเพื่อเลื่อนตำแหน่งเสียงทีละ 25ms หรือกด Shift พร้อมลูกศรเพื่อเลื่อนทีละ 5ms, Home/End เพื่อไปยังขอบเขตช่วงที่มองเห็น

### สีของภาพ

- คลื่นสีฟ้า — Peak Envelope จากค่า PCM จริง ไม่ได้ประดิษฐ์รูปคลื่นเพื่อให้สวย
- พื้นหลังน้ำเงิน — Speech Segment; ชมพูเข้ม — Silence/Mask
- พื้นที่สีเขียว — Cue จาก JSON ที่ผู้ใช้กำหนด (อาจยังไม่ได้บันทึก; ต้องกดปุ่มบันทึก Cue ในงาน)
- เส้นแดง — ตำแหน่งของ Audio Player; สีเหลือง — ช่วงเวลาที่เลือก

Waveform ปรับ Canvas ตามขนาดแผงและ HiDPI/Retina (DPR ไม่เกิน 2) เพื่อให้ไม่เบลอเมื่อใช้หน้าจอความละเอียดสูง

## ข้อมูลและการป้องกัน

- ไม่เก็บ WAV เพิ่มลง Disk โดย Waveform Editor; โหลด WAV จาก Speech Job ใน Browser เมื่อผู้ใช้ขอเท่านั้น
- จำกัด WAV ตามขนาดสูงสุดที่ Speech Coordinator อนุญาต (16MB) เพื่อลดความเสี่ยงการใช้หน่วยความจำเกิน
- ใช้ Peak Envelope ขนาด Block ละ 256 Samples; เมื่อซูมลึกเกิน Block Resolution ไม่อ้างว่าเห็น Sample ทุกตัว
- การคลิกลากหรือ Mark จะเปลี่ยนแค่ **เวลาในฟอร์ม** ยังไม่บันทึก Cue/ส่ง Subtitle ไป OBS จนกดเพิ่ม Cue และใช้เวลา Subtitle ในงานนี้
- ขอบเขต Cue ถูกตรวจซ้ำโดย Server ว่าเป็นช่วงเวลาใน Speech, ข้อความตรงกับ Display Text ที่ผ่าน Filter, และไม่ตัด Unicode/Emoji ผิดตำแหน่ง
- ไม่มี ASR ไม่มี Word/Syllable Alignment อัตโนมัติ และไม่รับประกันว่าจุดเริ่มเสียงตรงกับจุดเริ่มคำแบบแม่นยำระดับ Phoneme

## Benchmark ภาษาไทยที่ทำได้หลังมี Reference

การเทียบความแม่นยำของ Aligner ที่จะพัฒนาต่อ ต้องเก็บ **เสียงภาษาไทยที่ผู้ใช้เป็นเจ้าของสิทธิ์** และ Manual Cues ที่ผู้ฟังตรวจเวลาจริงโดยใช้ Waveform Editor; ไม่ควรใช้ชุดข้อมูลเสียงที่ไม่แน่ใจสิทธิ์

แนะนำเริ่มทดลองหลายประเภทที่ต่างกัน เช่น ประโยคสั้น, ประโยคยาว, ตัวเลข, คำทับศัพท์, สระ/วรรณยุกต์ที่ชิดกัน, พักหายใจ, เสียงพูดเร็ว–ช้า แล้วตรวจแยกตำแหน่งในหลายช่วงของ WAV. หากยังไม่มี Reference Cues ที่ตรวจฟังจริง จะ **ยังไม่สามารถรายงาน Accuracy ของ Forced Aligner ได้**

### วิธีประเมิน

วาง Candidate และ Reference Timecodes ใน JSON ของหน้า Manual Alignment แล้วกด **วัด Timing Error เทียบ Reference**. API จับคู่ด้วย segment_index + start_offset + end_offset เพื่อป้องกันการเปรียบเวลาคนละคำ และรายงาน Coverage, Mean Absolute Boundary Error (ms), Max Error และสัดส่วนขอบเขตที่คลาดเคลื่อนไม่เกิน 100ms. ตัวเลขนี้เป็นคุณภาพ **Timing เมื่อมี Reference**, ไม่ใช่คะแนนความถูกต้องการอ่านภาษาไทย

## การพัฒนาต่อ

- การบันทึก Reference แบบผูก Hash ของ WAV และ Hash ของ Display Text เพื่อป้องกันนำ Cue เก่าไปใช้กับเสียงอื่น
- เลื่อนเล่น Loop ตามช่วงที่เลือกและความเร็ว Playback เพื่อช่วย Mark คำเร็วขึ้น
- เพิ่ม Automatic Aligner เมื่อผ่าน Commercial-First Audit ครบทั้ง Code, Weights, Training Data และ Voice Rights

ดู [Manual Alignment](MANUAL_ALIGNMENT_TH.md), [API](API.md) และ [Commercial License Policy](COMMERCIAL_LICENSE_POLICY_TH.md).
