# VoxWeaveTTS v0.5.1 — Configurable Emoji Pronunciation (Windows Portable)

This Windows Portable update builds on v0.5.0 and adds **per-source emoji and emote pronunciation dictionaries** for **YouTube LIVE (API)**, **YouTube LIVE (Browser)**, **Discord (Bot)**, and **Discord Client**. Each source saves its own choices. TikTok remains chat-only; gift reading is still intentionally removed.

## New in v0.5.1

- Under **กำหนดการอ่านข้อความและข้อมูลพิเศษ**, enable **อ่านอีโมจิด้วยคำที่กำหนดเอง** and enter one mapping per line, such as:
  ```text
  😂 = หัวเราะ
  ❤️ = หัวใจ
  GGWP = เก่งมาก
  :party_parrot: = นกเต้น
  ```
- Map Unicode emoji (including multi-codepoint flags, joined sequences and skin tones), custom emoji codes such as `<:party_parrot:123456789012345678>` / `<a:party_parrot:123456789012345678>`, and named emotes such as `GGWP` or `catJAM`.
- Named emote replacements match **whole tokens**, not substrings: a `GGWP` mapping does not rewrite `GGWPXYZ`, `@GGWP`, or part of a custom emoji ID.
- YouTube Browser now preserves image-based emotes using the image `alt` label (when supplied by the page) and inserts boundaries around named emotes to keep them distinct from surrounding text.
- Dictionary hints and errors use **neutral wording** rather than calling the input Discord-specific. An entry such as `GGWP = เก่งมาก` is accepted.
- Up to **64 emoji mappings per source**, off by default. The original incoming chat and source fields are not rewritten; only the text sent for speech synthesis is transformed. Old portable preferences migrate automatically.
- Updated user guide: [Emoji Pronunciation (Thai)](https://github.com/funggier/VoxWeaveTTS/blob/v0.5.1/docs/EMOJI_PRONUNCIATION_TH.md).

## Downloads

- `VoxWeaveTTS-v0.5.1-portable.zip` — Windows x64 self-contained app, MakHam Paradee ONNX CPU voice, embedded Python, Web UI, and Chrome extension folder.
- `VoxWeaveTTS-TikTok-Extension-v0.2.4.zip` — optional standalone extension package; **extension code is unchanged** from v0.5.0.
- `SHA256SUMS-v0.5.1.txt` — SHA-256 for these ZIP files.

Optional **Vachana Thai 4 Voices** and **FastThaiG2P Thai Som** model packages remain available in the [v0.4.4 release](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.4.4).

## Quick start

1. Extract the **entire Portable ZIP** to any writable directory; do not run from inside the archive.
2. Launch `VoxWeaveTTS.exe` (fallback `Start-Console.cmd`).
3. Open `http://127.0.0.1:8765/`, choose your YouTube LIVE or Discord workspace, and expand **กำหนดการอ่านข้อความและข้อมูลพิเศษ**.
4. Tick **อ่านอีโมจิด้วยคำที่กำหนดเอง**, enter mappings (for example `GGWP = เก่งมาก`), and **save the speech-reading settings for that source**.
5. Test with a newly received message. A configured emote must be present as an exact Unicode sequence, `:name:` code, or a standalone named emote for replacement.

## Important limitations

- The reader can replace only emoji or emote tokens actually delivered in the message text or represented by an `alt` label in the YouTube Browser DOM. It does not recognize arbitrary images by vision.
- Named emote recognition is case-sensitive. If the service provides only `<:name:id>` syntax, configure a matching `:name:` or full-token mapping.
- The default behavior for unmapped emoji is unchanged; pronunciation by the selected TTS engine may vary.
- Global text replacement rules are independent and may still modify content; disable any earlier global `@` replacement if you want sender-specific handling only.
- Live receipt in each external provider is subject to provider access and DOM behavior. TikTok LIVE **reads comments only**, without Gift, Follow, Join, Like or Share speech. The TikTok Extension is community/dev tooling, not an official TikTok integration.
- Bundled models and dependencies have third-party terms; see `THIRD_PARTY_NOTICES.txt`.

## Thai overview

รุ่นนี้เพิ่มตัวเลือกอ่านอีโมจิสำหรับ YouTube LIVE และ Discord พร้อมกำหนดคำอ่านเอง เช่น `😂 = หัวเราะ`, `GGWP = เก่งมาก` โดยการตั้งค่าของแต่ละโหมดไม่ปะปนกัน ระบบจะเปลี่ยนเฉพาะข้อความที่ส่งสร้างเสียง ไม่แก้ข้อความต้นฉบับในแชท ค่าเริ่มต้นปิดไว้ และสามารถใช้การตั้งค่ารุ่นเก่าได้ตามเดิม
