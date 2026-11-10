# Audio Activity Alignment — Engine-Neutral Core

> สถานะ: v0.3.0.dev6 (ทดลอง) · **ไม่ใช่ Forced Alignment รายคำ** · ไม่มีโมเดลและไม่มี Dependencies ใหม่

## เป้าหมาย

ระบบเดิมมี Segment Timing จากจำนวน Sample ที่ Render แล้ว และ Estimated Subtitle ที่แบ่งเวลาภายใน Segment ตามจำนวนอักขระเท่านั้น รอบนี้เพิ่มการวิเคราะห์ **สัญญาณเสียงจริงใน WAV** ด้วยพลังงานเสียง PCM เพื่อรู้ว่ามีช่วงเงียบอยู่ตรงไหน ช่วยซ่อน Caption ระหว่างช่วงที่ไม่มีเสียง แทนการแสดงข้อความยาวค้างตลอด Segment

การตรวจพลังงานเสียง **ไม่สามารถระบุคำหรือพยางค์ที่กำลังพูด** ได้ จึงไม่ใช่ Word-Level Forced Alignment และไม่ได้อ้างความแม่นยำระดับคำ. เสียงดนตรี เสียงรบกวน หรือเสียงพูดเบามากอาจทำให้ผลผิดได้

## ขั้นตอน

1. Engine ใดก็ได้สร้าง WAV ผ่าน SpeechCoordinator เดิม
2. PCMActivityProvider วิเคราะห์ WAV แบบ Mono PCM16 8–96 kHz ด้วย Python Standard Library (wave, array, math) และคำนวณ RMS ตามหน้าต่างเวลา 20 ms โดยลดจำนวน Sample ระหว่างคำนวณ
3. เลือก Threshold จากพลังงานสูงสุดของ Speech Segment และค่าขั้นต่ำ รวมช่วงเสียงที่ห่างกันน้อยกว่า 100 ms และขยายขอบ 20 ms
4. ส่งผลเป็น activity_intervals ใน Timeline Metadata โดยไม่ส่ง Waveform ดิบ ข้อความต้นฉบับ หรือคำที่ถูกกรอง
5. Browser Playback Clock รายงาน audio.currentTime ตามจริง ส่วน Overlay ซ่อน Subtitle เมื่ออยู่ในช่วงที่ตรวจว่าเงียบ

ถ้าวิเคราะห์ WAV ไม่ได้ เช่น Stereo หรือ Format ไม่รองรับ ระบบจะใช้ Segment Timing เดิมแทน และรายงาน subtitle_precision = generated_segment_fallback_no_activity. การวิเคราะห์ไม่สำเร็จไม่ควรทำให้ WAV ที่สร้างสำเร็จแล้วล้มเหลว

## โหมด OBS Overlay

| URL | Mode | พฤติกรรม |
|---|---|---|
| http://127.0.0.1:8765/overlay | segment | Subtitle ตาม Segment ที่ได้จาก Audio Samples |
| http://127.0.0.1:8765/overlay?mode=estimated | estimated | แบ่งข้อความเป็นช่วงย่อยที่ประมาณเวลา |
| http://127.0.0.1:8765/overlay?mode=activity | activity | ซ่อน Subtitle ในช่วงที่ PCM ไม่มีพลังงานเสียง |

**Activity Mode ยังแสดงข้อความทั้ง Segment เมื่อมีเสียง** ไม่ได้เปลี่ยนข้อความทีละคำ ถ้าไม่ต้องการ Caption ขาดช่วงระหว่างคำ ให้ใช้ Segment Mode

## API ที่เพิ่ม

GET /v1/jobs/{speech_id} เมื่อพร้อมส่ง:
- audio.activity_basis = pcm16_mono_rms_energy_20ms_heuristic หรือ unavailable
- audio.word_alignment = false
- audio.segments[].activity_intervals = Array ของ {start_ms, end_ms} โดยแต่ละช่วงอยู่ภายใน Segment เดิม

GET /v1/playback/state?mode=activity และ GET /v1/playback/stream?mode=activity ส่ง Subtitle พร้อม subtitle_precision ที่ระบุว่าเป็น PCM Energy Heuristic หรือ Fallback

## แนวทางสำหรับโมเดลในอนาคต

โมดูล src/voxweavetts/audio_alignment.py ประกอบด้วย AudioAlignmentProvider (Protocol) และ PCMActivityProvider ตัวเริ่มต้น SpeechCoordinator รับ alignment_provider= เป็นตัวเลือก จึงสามารถเพิ่ม Provider อื่นโดยไม่แก้ TTS Engine Adapter ได้

การนำโมเดล Forced Aligner เข้ามาในอนาคตต้องตรวจสิทธิ์ของ Source Code, Model Weights และ Training Data แยกกันตาม Commercial-First Policy ก่อนรวมในโปรเจกต์

## การทดสอบและข้อจำกัด

- ไม่มี External Model Download และไม่มี Dependencies เพิ่ม
- จำกัดไม่เกิน 32 Activity Intervals ต่อ Segment
- Activity Provider ไม่เก็บ WAV หรือข้อความต้นฉบับลง Disk
- Regression: PCM Synthetic Tone/Silence, Timing Bounds, Privacy/Mask, Coordinator Mock, Playback API และ SSE
- ยังเหลือ True Word/Syllable Forced Alignment, Thai Dataset/Quality Benchmarks และ Hardware Audio-Output Clock

ดู [Playback/OBS Guide](PLAYBACK_OVERLAY_TH.md), [Engine-Neutral Core](ENGINE_NEUTRAL_CORE_TH.md) และ [Commercial Policy](COMMERCIAL_LICENSE_POLICY_TH.md)
