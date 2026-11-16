# VoxWeaveTTS v0.9.2 — Complete Mixed-Language TTS Release (Windows Portable)

**Release date:** 2026-11-16 · Windows 10/11 x64 · [README ภาษาไทย](../README_TH.md) · [Mixed-language guide](MIXED_LANGUAGE_TTS_TH.md) · [Previous v0.9.1](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.9.1)

**Complete release.** Includes all v0.9.1 multilingual voices, Japanese pronunciation fixes, Chinese `555` laughter fixes, translations, live queue integrations, independent per-mode settings, and the new **opt-in mixed-language speech synthesis into one WAV**. The main ZIP includes a Windows launcher, self-contained Python 3.11 CPU runtime, local Web UI, and the MakHam Paradee Thai model. Optional models are separate downloads. No user accounts, tokens, personal settings, presets, chat records, voice recordings, or trained private voices are distributed.

## What's new in v0.9.2

### One utterance, several language models, one WAV

- New independent switch in **กำหนดการอ่านข้อความและข้อมูลพิเศษ** for every speech mode: **แยกอ่านข้อความตามภาษา (รวมเสียงเป็นไฟล์เดียว)**. Defaults **OFF**, and each workspace saves its own preference without changing the prior whole-message route switch.
- With the switch **ON**, `ผมอยากทำComputer ผม ให้มันลื่นกว่านี้ lol` is processed in this exact order: **th** `ผมอยากทำ` → **en** `Computer ` → **th** `ผม ให้มันลื่นกว่านี้ ` → **en** `lol`.
- Each span uses its own saved Engine, Model, Voice, speed, seed, and DSP controls. The renderer concatenates samples into **one PCM16 mono WAV** and returns a single subtitle timeline, without inserting extra live-chat queue jobs.
- Handles un-translated mixed-language input and **partially translated** content: segmentation follows the text *actually passed to speech synthesis*, even when AI translation target is set to a different language. Translation processing and post-AI filtering are not replaced.
- Resamples independent models with different sample rates (e.g. Kokoro 24 kHz, MeloTTS Chinese and Supertonic 3 44.1 kHz) before concatenation. Retains source order and existing masked/skip/silence handling.
- When a language has no configured route, its span uses the workspace **Default Engine / Model**. A configured but unavailable model fails explicitly instead of silently substituting another engine. Maximum 96 detected speech spans per job to bound CPU/memory work.
- **Important limitation:** Language detection is a conservative **Unicode-script heuristic**: Latin defaults to English (cannot reliably distinguish French/German/Spanish), Cyrillic defaults to Russian; Han next to Japanese kana is Japanese, isolated Han generally Chinese. Punctuation/whitespace stays with its preceding span. Not a full AI language identifier, not guaranteed word-level subtitle alignment.

### Kept from v0.9.1 (included, not removed)

- Kokoro Japanese TTS uses Misaki Japanese G2P + UniDic Lite (avoids repeatedly reading `Japanese letter` / `Chinese letter` for Japanese text such as `多分殻ごと食ってるもんね`).
- Optional local CPU TTS packages: MeloTTS Chinese (`zh_melo`) and Supertonic 3 for Korean and 30 further languages; independent language/voice mapping prevents cross-language leakage.
- Translation-to-Chinese `555` laughter fix (Chinese `哈哈哈`; Thai `ฮ่า ฮ่า ฮ่า`; Japanese `ははは`; Korean `하하하`) with optional `spoken_by_language` rule overrides.
- FIFO queue semantics by default, optional random backlog reduction, YouTube Top/Live comment manual selection, Discord and TikTok Extension reading, shared OBS subtitles, per-mode voice presets, Ollama AI Translation and structured Custom Prompt, experimental offline M2M100 and Ollama Speech adapters.

## Complete download set (9 GitHub Release assets)

1. **`VoxWeaveTTS-v0.9.2-portable.zip`** — main Windows Portable (bundled MakHam Paradee Thai voice; no installer).
2. **`VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel`** — optional Thai Som TTS.
3. **`VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel`** — optional four Thai voices.
4. **`VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel`** — optional Kokoro voices, English and Japanese among supported languages.
5. **`VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel`** — optional Mandarin Chinese TTS.
6. **`VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel`** — optional Korean and 30 additional languages.
7. **`VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel`** — optional **translation**, experimental; PyTorch/Transformers/SentencePiece runtime not bundled.
8. **`VoxWeaveTTS-TikTok-Extension-v0.2.5.zip`** — optional TikTok LIVE browser extension.
9. **`SHA256SUMS-v0.9.2.txt`** — SHA-256 checksums for the other **8** binary archives.

The five TTS packages are **optional**; only the MakHam voice comes inside the Portable ZIP. Install only the models you plan to use. The individual `.vwmodel` files are identical model data as v0.9.1, with notices and checksum validation; the new capability is in the **application/runtime**. Model data files are not added to Git history.

## Installation / upgrade from v0.9.1

1. Download `VoxWeaveTTS-v0.9.2-portable.zip` and unpack into a **new writable folder** on any drive. Close the previous instance before running `VoxWeaveTTS.exe` or `Start-Console.cmd`. Access the Web UI at `http://127.0.0.1:8765/`.
2. Keep a backup and copy **only personal data you choose** from the older Portable: `data/`, `presets/`, locally installed model packages under `models/packages/`, AI models, and your own voice resources. **Never replace** the new `runtime/`, `src/`, `web/`, or executable with the old version.
3. Download/install optional TTS `.vwmodel` packages in the Model Package Manager; install AI M2M100 in its separate AI Model Package interface if you have its additional runtime.
4. In **โมเดลเสียงตามภาษา**, configure entries such as **th → MakHam**, **en → Kokoro**, **zh → MeloTTS Chinese**, **ko → Supertonic 3**, **ja → Kokoro Japanese**. Check that the model package is ready in the Engine Registry.
5. Under your desired mode's **กำหนดการอ่านข้อความและข้อมูลพิเศษ**, turn on **แยกอ่านข้อความตามภาษา (รวมเสียงเป็นไฟล์เดียว)**. This feature is **off by default**. It is independent of the existing **ใช้การเลือกโมเดลตามภาษา** switch, so you may enable or disable either one separately.
6. Test with `ผมอยากทำComputer ผม ให้มันลื่นกว่านี้ lol` and inspect the produced single WAV. The default engine remains a fallback if a span has no route.

## Test evidence and limitations

- Python unit/integration tests: mixed-language segmentation, per-workspace HTTP setting persistence, same-engine voice changes, resampling, common subtitle timeline, disabled-mode backward compatibility, and partially-translated text.
- JavaScript smoke tests: per-mode toggle saves independently and defaults off.
- Real CPU model test using the **embedded Portable Python**: Thai + English `th/en/th/en` WAV (24 kHz), and Thai + Chinese + Korean + English WAV (44.1 kHz), using separate `.vwmodel` assets installed into a temporary test location. ZIP integrity checked.
- Actual live network sources (YouTube/Discord/TikTok), every possible language, human listening quality, long-running memory usage and real-world translation accuracy are **not certified** by these tests.

**License obligations:** The application's own code uses MIT, but bundled third-party components and voice packs retain their **own licenses**. Supertonic 3 is under **BigScience OpenRAIL-M with restrictions**, not unrestricted MIT; MeloTTS Chinese model card reports MIT but voice/training rights have not been independently audited; FastThaiG2P Som training credits include CC BY 4.0; bundled eSpeak NG uses GPL-3.0 redistribution obligations. Review the included notices for each package; no universal commercial-use guarantee is provided.

Documentation: [Thai mixed-language walkthrough](MIXED_LANGUAGE_TTS_TH.md), [31-language engine notes](MULTILINGUAL_31_LANG_TH.md), [Model Package catalog](../model-packs/README_TH.md), [AI translation](AI_PROCESSING_TRANSLATION_TH.md), [Queue behavior](LIVE_QUEUE_POLICY_TH.md), [License policy](COMMERCIAL_LICENSE_POLICY_TH.md).
