# VoxWeaveTTS v0.9.1 — Complete Multilingual TTS & Japanese/Chinese Speech Fixes

**Release date:** 2026-11-16 · Windows 10/11 x64 · [All releases](https://github.com/funggier/VoxWeaveTTS/releases) · [ภาษาไทย](../README_TH.md)

This is a **full Windows Portable release** incorporating all features of v0.9.0 plus the completed Japanese, Chinese, Korean and multilingual TTS work. Install model packages independently; only the MakHam Paradee Thai model is included in the main ZIP. No private voice presets, credentials, locally saved settings, chats or recordings are shipped.

## Download package list

1. `VoxWeaveTTS-v0.9.1-portable.zip` — portable app, Windows EXE, Python 3.11 and CPU ONNX runtimes, Kokoro/Misaki Japanese G2P, sherpa-onnx for Chinese/Korean, Web UI, OBS/queues, preinstalled **MakHam Paradee** Thai voice.
2. `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` — optional Thai Som model.
3. `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel` — optional 4 Thai voices.
4. `VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel` — optional 18 Kokoro voices in seven languages including Japanese, now with the correct Japanese G2P path.
5. `VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel` — optional Mandarin Chinese speech, CPU ONNX.
6. `VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel` — optional Korean plus 30 other languages, CPU ONNX; 62 voice/language selectors (2 per language), model uses OpenRAIL-M.
7. `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` — optional experimental offline **translation** model (Torch/Transformers/SentencePiece runtime not included).
8. `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip` — optional Chrome extension for TikTok LIVE browser chat.
9. `SHA256SUMS-v0.9.1.txt` — SHA-256 checksums for all eight binary archives above.

All optional TTS model packages are separately downloadable; you do **not** need to download all models to run the default Thai TTS. Model weights are not committed to Git history.

## Changes since v0.9.0

### Japanese Kokoro voice pronunciation

- Previous ONNX wrapper routed Japanese text through eSpeak. Japanese kanji in `多分殻ごと食ってるもんね` were pronounced as repeated "Chinese letter" or "Japanese letter" despite a Japanese voice selection.
- Japanese Kokoro voices now use **Misaki Japanese G2P + UniDic Lite**, feeding `is_phonemes=True` to Kokoro; other language voice paths are unchanged. The Portable runtime bundles the required Japanese phonemizer and dictionaries. Missing Japanese G2P fails explicitly rather than silently using English/eSpeak.

### Chinese & Korean and 31-language ONNX support

- New local CPU `sherpa-onnx==2.0.1` trusted voice adapters and data-only `.vwmodel` model packages: **MeloTTS Chinese** (`zh_melo`, 44.1 kHz) and **Supertonic 3** (`ko_s0`, `ko_s1` and 30 other supported languages, 44.1 kHz).
- Per-language settings support independent Engine/Voice selection even when multiple languages use the **same engine**. A per-voice language mapping is passed to Supertonic on each request; this prevents one language's G2P/voice context leaking into another.
- Supported Supertonic languages: ar, bg, hr, cs, da, nl, en, et, fi, fr, de, el, hi, hu, id, it, ja, ko, lv, lt, pl, pt, ro, ru, sk, sl, es, sv, tr, uk, vi.
- **Important:** spoken-language automatic detection is script-based and cannot reliably distinguish every language sharing Latin or Cyrillic scripts. Set explicit language mapping where possible; this release is not a universal word-by-word mixed-language voice switching solution.

### Chinese `555` laughter bug after translation

- Reproduced a job with the Thai source `ชายหนุ่มกลายเป็นอมตะ และพูดคำต้องห้าม ก่อนหัวเราะ 555`. If translation preserved `555`, the legacy post-AI rule replaced it with Thai-only `ฮ่า ฮ่า ฮ่า` inside Chinese speech. MeloTTS reported out-of-vocabulary Thai symbols and a failed conversion to token IDs. **Seed 100 was not the cause.**
- Post-AI five-run laughter replacement now uses the destination speech language: Chinese `哈哈哈`, Japanese `ははは`, Korean `하하하`, English `ha ha ha`, Thai `ฮ่า ฮ่า ฮ่า`. The original `555` remains in the subtitle. Custom language-specific `spoken_by_language` rule overrides are supported, without rewriting arbitrary user-defined replacements.
- The preserved processing order is mode rules → shared pre-AI rules → translation → shared post-AI rules with language-aware pronunciation → TTS.

### Retained v0.9.0 functionality

FIFO Live/Discord/TikTok queues by default; optional overflow random reduction (disabled by default, >20 keep 5), manual YouTube Top/Live chat selection, background reader/Firefox handling, non-disruptive queue reset, per-mode/per-language voice settings, custom voice presets, Ollama Translation/Custom Prompt tools, experimental structured M2M100 and Ollama Speech adapters. There are no new credentials or provider OAuth requirements in this release.

## Install and upgrade

1. Download the Portable ZIP, extract to a **new writable folder**, then start `VoxWeaveTTS.exe` (or `Start-Console.cmd` to troubleshoot). Open `http://127.0.0.1:8765/`.
2. Close the old instance first. Back up and selectively copy only **your own** data from the previous portable folder: `data/`, `presets/`, installed `models/packages/`, `models/ai/` and personal voices if applicable. Do **not** overwrite the freshly extracted `src/`, `web/`, `runtime/` or EXE files.
3. Download optional `.vwmodel` assets needed for your languages. Install TTS model packs via **ตั้งค่า → จัดการ Model Packages**. Use the separate AI Model Packages UI for M2M100.
4. In **โมเดลเสียงตามภาษา**, assign e.g. `zh → MeloTTS Chinese / zh_melo`, `ko → Supertonic 3 / ko_s0`, `ja → Kokoro / jf_nezumi`. Enable `ใช้การเลือกโมเดลตามภาษา` for each relevant workspace. Translation target and chosen TTS language should agree.
5. Test the Chinese `555` sentence. If translation settings have conflicting trusted Prompt/Restrictions (e.g. target Chinese but prompt requests Thai), adjust them; language routing cannot repair an intentionally wrong-language translation.

## Validation and known limitations

- Python regression suite, JavaScript UI smoke suite, unpackaged Japanese Kokoro real WAV, Chinese MeloTTS 555 real WAV (Seed 100), Korean Supertonic real WAV, and Portable embedded Python runtime tests were run during development. Full testing of every language and all remote Live providers is not claimed.
- M2M100 is experimental and requires a separately installed compatible ML runtime; no PyTorch weights or dependencies bundled. Live translations still depend on the chosen local model and user-configured prompting.
- **License responsibilities:** Application MIT; the Portable embeds third-party code and eSpeak NG GPL-3.0 source/notice obligations (see notices and policy). MeloTTS Chinese model card declares MIT; **Supertonic 3 is OpenRAIL-M with use restrictions**, not MIT. Vachana/Kokoro/FastThaiG2P and other voice/training datasets are **review_required**, not unconditionally approved for all commercial uses. Optional model package notices and model manifest checksums are provided.
- No automatic voice cloning/training or guaranteed word-level subtitle alignment. Live provider behavior, user hardware and microphone/speaker autoplay policies vary.
- Keep the `SHA256SUMS-v0.9.1.txt` file when archiving, and verify SHA-256 against each downloaded asset.

See [Multilingual setup and limitations](MULTILINGUAL_31_LANG_TH.md), [Thai TTS language routes](MULTILINGUAL_TTS_TH.md), [Model package catalog](../model-packs/README_TH.md), [Translation setup](AI_PROCESSING_TRANSLATION_TH.md), [Queue rules](LIVE_QUEUE_POLICY_TH.md), [Portable setup](PORTABLE.md), and [License policy](COMMERCIAL_LICENSE_POLICY_TH.md).
