# VoxWeaveTTS v0.9.0 — Windows Portable + Complete Model Packages

**Release date:** 2026-11-16 · [Repository](https://github.com/funggier/VoxWeaveTTS) · [คู่มือภาษาไทย](../README_TH.md)

This is a full Windows x64 Portable release containing the changes made after v0.8.0. **All six binary/model archives are published as separate downloads alongside a SHA-256 checksum file.** The main ZIP remains portable: unzip, launch and keep your own settings, models and caches inside the application folder.

## Download all seven assets

| File | Contents |
| --- | --- |
| `VoxWeaveTTS-v0.9.0-portable.zip` | Windows 10/11 x64 application, embedded Python 3.11 runtime, MakHam Paradee Thai CPU ONNX voice, Kokoro CPU/eSpeak dependencies, Windows EXE launcher, Web UI, OBS, Live chat and audio queue |
| `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` | Optional Thai Som voice, FastThaiG2P model package (Apache-2.0 upstream; Som TTS training data CC BY 4.0) |
| `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel` | Optional 4 Thai voices (upstream MIT model card; third-party voice/training rights not independently audited) |
| `VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel` | Optional 18 voices in English, Spanish, French, Hindi, Italian, Japanese, Portuguese (CPU ONNX INT8, Apache-2.0 upstream model card; voice/data rights not independently audited) |
| `VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel` | Experimental offline translation weights (requires additional PyTorch, Transformers, SentencePiece runtime; **not** bundled in Portable) |
| `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip` | Optional Chrome extension for reading TikTok Live comments, manually installed |
| `SHA256SUMS-v0.9.0.txt` | Checksums for all six distributed archives; verify before extraction or installation |

**Only MakHam Paradee voice weights are bundled in the main Portable ZIP.** Optional model archives are unchanged from v0.8.0 and republished for a complete one-page download. No private settings, OAuth/API credentials, recordings or personal model weights are included.

## What's new since v0.8.0

### Live comment read queue and YouTube Browser

- By default, **read accepted incoming Live comments in FIFO arrival order without the previous 12-message frontend / 40-message backend overflow skips.** Completed-chat display history is a separate limit; hiding older read messages does not delete unspoken items.
- Add **สุ่มลดคิวเมื่อสะสมมากเกินกำหนด**, disabled by default on all six Live/Discord/TikTok chat readers. If the **waiting** queue grows **beyond 20**, randomly retain **5** waiting messages, then read those survivors in their original arrival order. The trigger and keep count are editable. It never selects a currently translating/synthesizing/playing message; skipped items are labeled separately.
- Add an explicit **รีเซ็ตคิวข้อความ** button to clear waiting entries on the client and source server while keeping the currently active message uninterrupted and leaving Live connections open.
- **YouTube LIVE (Browser) no longer changes Top chat to Live chat automatically.** You choose the YouTube menu in the separate Chat-only Chrome/Edge window. Top chat may be filtered by YouTube, before VoxWeaveTTS receives any messages.
- Firefox autoplay interruptions retain pending messages and prepared WAV for retry. Creating a manual speech preview no longer silently erases the accepted Live queue; interrupted active Live speech is placed back at the front.
- Source queues are no longer count-capped, so unbounded chat rates can still consume RAM. Enable optional random reduction when a high-volume chat must stay responsive. Normal content filters, provider delivery limits, explicit Stop/Reset and transcription/translation errors still apply.

### AI Translation and Custom Prompt

- **Ollama Translation:** simplified JSON Schema output `{"translation":"..."}`, with raw chat text isolated as untrusted data. Strict parsing prevents TTS from speaking JSON field names or instructions.
- **Ollama Custom Prompt:** JSON Schema `{"result":"..."}`; the selected target output language now applies to Custom Prompt, and saved Priority Instructions are above saved Custom Prompt. Workflow dropdown: **ไม่ระบุ** (default, both saved prompt fields decide), **แปลอย่างเดียว**, **ตอบคำถามแทนการแปล**, **แปลคำถามและตอบต่อท้าย**. Incoming chat may be analyzed and answered when configured, but cannot independently modify trusted instructions or tool permissions.
- **Translation accuracy bypass:** optional, disabled by default, for Ollama Translation and M2M100. It bypasses heuristic meaning/script checks only; output structure, text-length and control-character restrictions remain.
- **M2M100 Structured Pipeline:** keep language metadata outside the translation input, split long messages without silent tokenizer truncation, assemble in source order, conservatively handle Han-only Chinese/Japanese ambiguity. **This is not a translation-accuracy upgrade**: the actual model still failed 2/3 previous semantic sample cases.
- **Ollama Speech adapter:** experimental opt-in engine registration and WAV/PCM integration only. No automatic model download. It requires a compatible speech-capable Ollama server; a Windows-native supported speech runtime and actual Phonon end-to-end synthesis have **not** been verified, and this release does **not** bundle a Phonon or Qwen3-TTS model.

### Existing features retained

- Per-language Voice Engine/Voice/tuning profiles and shared Voice Presets; MakHam, optional Vachana, FastThaiG2P and Kokoro.
- Document/Narration, YouTube LIVE (API and Browser), Discord Bot and Desktop Client, TikTok/TikFinity and TikTok Extension; global translation Rules and replacement dictionaries; shared speech queue and OBS subtitles.
- Local-only/LAN-authorized Ollama processing, restricted opt-in read-only AI tools, token-gated source drain/reset, portable file-based settings and package manager.

## Install / upgrade

1. Download **`VoxWeaveTTS-v0.9.0-portable.zip`** and extract it to a **new, writable folder** (do not run the EXE inside ZIP). Launch `VoxWeaveTTS.exe` or `Start-Console.cmd` and open http://127.0.0.1:8765/.
2. If upgrading from v0.8.0, **stop the old instance first**. Back up its `data/`, `models/packages/`, `models/ai/`, `presets/` and any personalized voice files. **Copy only your own trusted settings and optional installed packs** into the new folder; do not overwrite the fresh `src/`, `web/` or `runtime/` directories.
3. Download only the optional `.vwmodel` packages you intend to use. Install TTS packs from **ตั้งค่า → จัดการ Model Packages**; M2M100 installs through the AI model package panel and still requires separate compatible runtime.
4. For a high-volume Live chat, adjust **สุ่มลดคิวเมื่อสะสมมากเกินกำหนด**. It stays **off** unless you enable it, keeping all accepted pending messages in FIFO order. On YouTube Browser choose **Top chat / Live chat manually** within YouTube.

## Verification and limitations

- SHA-256 of every attached asset is in `SHA256SUMS-v0.9.0.txt`. The release process validates the existing optional packs against pinned upstream model hashes and legal notices, checks the Portable runtime and TTS synthesis, and runs Python/JavaScript regression tests.
- Real YouTube/Discord/TikTok delivery, Browser suspension and provider quotas cannot be guaranteed by mock tests. Firefox may still require a click to permit autoplay; speech speed depends on CPU, models and system conditions.
- Model/voice data permissions are as declared by their third-party publishers, **not independently certified for every commercial use**. eSpeak NG DLL/data uses GPL-3.0 and source/notice obligations; see the included third-party files and license policy. There is no voice cloning, voice training or guaranteed word-level subtitle alignment in this version.
- The optional **M2M100** weights do not include PyTorch/Transformers dependencies. **Ollama Speech** is a future-facing adapter, not an assurance of Windows Ollama native speech support.

Documentation: [Live Queue and Random Mode (Thai)](LIVE_QUEUE_POLICY_TH.md) · [AI/Translation (Thai)](AI_PROCESSING_TRANSLATION_TH.md) · [M2M100 (Thai)](M2M100_SETUP_TH.md) · [Ollama Speech (Thai)](OLLAMA_SPEECH_ADAPTER_TH.md) · [Portable Install](PORTABLE.md) · [License Policy](COMMERCIAL_LICENSE_POLICY_TH.md).
