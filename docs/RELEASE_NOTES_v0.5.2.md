# VoxWeaveTTS v0.5.2 — Guided Rules Builder and TikTok Emoji Pronunciation

Windows Portable update based on v0.5.1. This release includes the **full guided Rules quick-add form** and **opt-in emoji pronunciation for TikTok LIVE (TikFinity / Chrome Extension)**. Existing YouTube, Discord and document workspaces remain supported.

## What's new

### Guided Rules quick-add (Rules — กฎการอ่านและกรองคำ)

The quick-add section now supports all rule features accepted by the local text-processing backend:

- **Match mode**: literal text or the predefined `five_run` pattern (three or more consecutive fives, excluding numeric sequences in larger numbers).
- **Action**: `replace` (spoken replacement), `skip` (no speech), or `silence` (timed pause, 0–10,000 ms).
- **Output**: independent `spoken` and optional `display` (subtitle), with contextual controls.
- **Source filter**: apply to all sources or restrict to YouTube API, YouTube Browser, TikTok TikFinity, TikTok Extension, Discord, manual/API, and document input. Discord Bot and Discord Client currently share the `discord` source ID.
- **Preview and test**: live preview of the JSON object and a source selector for testing against the actual local text-processing API.
- Adding a rule only updates the editable **Rules JSON**. Click the separate **บันทึกในโปรแกรม** button to save to portable settings. Existing JSON imports/exports and conflict checks are preserved.

The editor does not advertise unsupported arbitrary regular expressions or case-insensitive matching. See [Rules quick-add guide (Thai)](https://github.com/funggier/VoxWeaveTTS/blob/v0.5.2/docs/RULES_QUICK_ADD_TH.md).

### TikTok LIVE emoji reading

- The **same opt-in emoji-to-pronunciation dictionary** that YouTube and Discord already have is now present in both TikTok LIVE (TikFinity) and TikTok LIVE (Extension), with independent per-mode settings.
- TikTok Chrome Extension **v0.2.5** can include emoji image `alt` labels in actual new comments (such as `😂`, `GGWP`) while continuing to exclude user rank/badge decoration from the spoken comment body.
- Example mapping: `😂 = หัวเราะ`, `❤️ = หัวใจ`, `GGWP = เก่งมาก`.
- **Gift, Follow, Join, Like and Share reading remains unsupported**; only chat comments enter the TikTok TTS feed. Unmapped emoji stay unchanged.

## Download files

- **`VoxWeaveTTS-v0.5.2-portable.zip`** — Windows 10/11 x64 portable application, embedded Python runtime, MakHam Paradee CPU voice model, Web UI, and TikTok Chrome Extension v0.2.5 in `extensions/tiktok-live-connector`.
- **`VoxWeaveTTS-TikTok-Extension-v0.2.5.zip`** — standalone Chrome Manifest V3 extension package for manual installation.
- **`SHA256SUMS-v0.5.2.txt`** — SHA-256 hashes of both ZIP assets.

Optional Vachana Thai 4 Voices and FastThaiG2P Thai Som model packs remain available from [v0.4.4](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.4.4); the main portable archive bundles only MakHam Paradee.

## Getting started

1. Extract the entire Portable ZIP to a **writable directory**. Do not launch directly from the ZIP.
2. Start `VoxWeaveTTS.exe` (or `Start-Console.cmd`). Visit `http://127.0.0.1:8765/` if it does not open automatically.
3. Open **Rules**, expand **เพิ่มกฎอย่างรวดเร็ว**, configure your match/action/source options, click **เพิ่มกฎลง JSON**, optionally test with the chosen source, then click **บันทึกในโปรแกรม** to persist.
4. For TikTok emoji speech, open either TikTok mode → **กำหนดการอ่านข้อความและข้อมูลพิเศษ** → enable emoji reading and enter `อีโมจิหรือชื่ออีโมจิ = คำอ่าน` mappings, then save.
5. If you use TikTok Extension, open `chrome://extensions` and **Reload** the extension from the **v0.2.5 folder** (using **Load unpacked** if upgrading from an older extracted ZIP), refresh the TikTok LIVE tab, then re-pair with the app.

## Notes

The Chrome extensions and browser DOM readers depend on what the external platform renders; delivery of actual LIVE chat is not guaranteed. This is not an official TikTok or YouTube integration. Rule matching remains case-sensitive for literal matches. No voice cloning or training is included. Existing local settings should be backed up before upgrading and may be copied into the new portable folder; the distributed ZIP does not contain user settings or credentials.

**ภาษาไทย:** รุ่น v0.5.2 เพิ่มฟอร์มสร้างกฎแทนคำ/ข้ามคำ/หยุดเสียงแบบละเอียด จำกัดแหล่งข้อความได้ และเพิ่มอ่านอีโมจิแบบกำหนดคำอ่านเองให้ TikTok LIVE ทั้งสองโหมด โดยยังไม่รองรับการอ่านกิจกรรมส่งของขวัญ
