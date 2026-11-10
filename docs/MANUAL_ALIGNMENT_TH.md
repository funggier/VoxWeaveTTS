# Manual Alignment Workbench — VoxWeaveTTS

> v0.3.0.dev7 (ทดลอง) | ไม่ต้องใช้ ASR หรือโมเดลภายนอก

## หลักการ

เมื่อ WAV ถูกสร้างสำเร็จ ผู้ใช้สามารถฟังเสียงและกำหนดจุดเริ่ม–จบของ Subtitle รายคำหรือวลีด้วยตนเองได้ โดยไม่ผูกกับ TTS Engine

นี่คือ **Manual Alignment ที่ผู้ใช้ตรวจเอง** ไม่ใช่ Forced Alignment อัตโนมัติ และไม่อ้างว่าโมเดลสามารถรู้ว่ากำลังพูดคำใดโดยตรง

## วิธีทดลอง

1. เปิด http://127.0.0.1:8765/ และกด Ctrl+F5 จากนั้นสร้าง WAV ผ่าน Speech Queue จนเป็น Ready
2. เปิดส่วน Manual Alignment แล้วกด โหลดงานล่าสุดที่ Ready เลือก Speech Segment
3. ไฮไลต์ข้อความที่ได้ยินในกล่องข้อความด้านบน
4. เปิดเสียงผ่าน Queue Audio Player แล้วกด จับเวลาเริ่มจากเสียง / จับเวลาจบจากเสียง หรือพิมพ์เวลาเป็น Milliseconds
5. กด เพิ่ม Cue จากข้อความที่ไฮไลต์ เพื่อเพิ่มช่วงเวลา Subtitle
6. กด ใช้เวลา Subtitle ในงานนี้ (ต้อง Pause เสียงก่อน) แล้วกด Play WAV ใหม่
7. เปิด http://127.0.0.1:8765/overlay?mode=manual เพื่อทดลอง Subtitle ใน OBS Browser Source

ส่วนที่ไม่ได้สร้าง Cue จะไม่แสดงข้อความใน Manual Mode. การแก้ Timeline ไม่มีผลกับไฟล์ WAV และยังใช้กับ TTS Engine ได้ทุกตัว

## JSON Cues

ตัวอย่าง:

    [
      {
        "segment_index": 0,
        "start_offset": 0,
        "end_offset": 5,
        "start_ms": 120,
        "end_ms": 510
      }
    ]

Offset ของข้อความนับแบบ Unicode Code Points ไม่ใช่ UTF-8 Bytes หรือ JavaScript UTF-16 Code Units. ระบบตรวจไม่ให้ตัดขาดกลางวรรณยุกต์ไทยและ Emoji แบบรวมอักขระที่รองรับ

Server จะสร้างข้อความแสดง Subtitle เองจากข้อความ Display ที่ผ่าน Rules/Mask/Filter แล้ว ไม่อนุญาตให้แทรกข้อความใด ๆ ลง Cue โดยตรง ไม่อนุญาต Cue บน Silence/Skip หรือช่วงเวลาที่ซ้อนกัน จำกัดสูงสุด 128 Cues ต่อ Job

### การเก็บข้อมูล

Alignment ที่บันทึกในงานจะอยู่ใน **หน่วยความจำของ Speech Job เท่านั้น** ไม่มีการสร้างไฟล์บน Disk อัตโนมัติ. หากต้องการเก็บเวลาที่ตรวจแก้ไว้ให้กด ส่งออก JSON

เมื่อนำเข้า JSON ที่เคยบันทึกเข้ากับงานใหม่ ต้องตรวจว่า WAV ใหม่มีระยะเวลาและคำอ่านตรงกับของเดิมจริง อย่าสมมติว่าการสร้าง WAV รอบใหม่มี Timing เท่าเดิม

## API

- GET /v1/jobs/{speech_id} คืน Audio Timeline พร้อม alignment_revision (เมื่อ Ready) และ manual_cues หากกำหนดแล้ว
- POST /v1/jobs/{speech_id}/alignment รับ JSON Object มี cues (Array) และ expected_revision (Integer). ต้องส่ง Header X-VoxWeaveTTS-Intent: save-manual-alignment
- GET /v1/playback/state?mode=manual และ GET /v1/playback/stream?mode=manual คืน Subtitle จาก Cue ที่ผู้ใช้ตรวจเอง และ subtitle_precision เป็น manual_user_timed หรือ manual_no_cues
- POST /v1/alignment/evaluate รับ candidate และ reference (Array) พร้อม Header X-VoxWeaveTTS-Intent: evaluate-manual-alignment; ไม่เก็บข้อมูลลง Disk

เมื่อแก้ Cue แล้วควรเริ่ม Audio Playback Session ใหม่เพื่อให้ระบบอ่าน Timeline ล่าสุด. หากมีคนแก้ข้อมูลจากอีกแท็บ Revision จะไม่ตรงและระบบตอบ HTTP 409

## วัดความคลาดเคลื่อนจาก Reference

กำหนด Reference Cues ที่ฟังตรวจเอง และนำ Candidate Timecodes มาเปรียบเทียบผ่านช่อง Reference Cues JSON ในหน้า Web

ตัวชี้วัด:

- matched_cues: จำนวน Cue ที่มี Segment Index และ Text Offset ตรงกัน
- reference_coverage_percent: ความครอบคลุมของช่วง Reference
- mean_absolute_boundary_error_ms: ค่าคลาดเคลื่อนเฉลี่ยของจุดเริ่ม/จบ (ms)
- max_absolute_boundary_error_ms: คลาดเคลื่อนสูงสุด (ms)
- boundaries_within_100ms_percent: ร้อยละขอบเขตที่คลาดเคลื่อนไม่เกิน 100 ms

หากไม่มี Cue ที่จับคู่ได้ ตัววัด Error เป็น null ไม่รายงานความแม่นยำปลอม. การเทียบตัวเลขไม่รับประกันว่าคำอ่านภาษาไทยถูกต้อง ต้องตรวจฟังและตรวจจุดเริ่มจบจริง

## Commercial-First / Limitations

- ไม่ติดตั้งโมเดล Pretrained ไม่ใช้ Dataset ภายนอก และไม่เพิ่มค่าใช้จ่าย Cloud
- ไม่มีการอัปโหลดข้อความหรือ WAV ออกนอก Local HTTP API
- การบันทึก Cue ในงานไม่เก็บเสียง/ข้อความลง Disk และถูกล้างเมื่อ Speech Job หมดอายุหรือปิด Server
- ยังไม่มี Acoustic Word Recognition, Auto Forced Alignment, Waveform Zoom, หรือระบบบันทึก Timecode ข้าม Session โดยอัตโนมัติ
- ถ้าพัฒนา Automatic Aligner ในอนาคต ต้องตรวจสิทธิ์ Source Code, Model Weights และ Dataset เชิงพาณิชย์ให้ครบก่อน

ดู [Playback/OBS](PLAYBACK_OVERLAY_TH.md), [Audio Activity](AUDIO_ALIGNMENT_TH.md), [Commercial Policy](COMMERCIAL_LICENSE_POLICY_TH.md)
