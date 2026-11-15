# VoxWeaveTTS v0.8.0 — Windows Portable + Complete Model Packages

Release date: 2026-11-15. Repository: https://github.com/funggier/VoxWeaveTTS

## Download assets (all supplied separately, same structure as v0.7.2)

1. VoxWeaveTTS-v0.8.0-portable.zip — main Windows 10/11 x64 app, MakHam Paradee Thai CPU ONNX, embedded Python runtime, Web UI, sources/OBS, additional Kokoro CPU runtime, executable launcher
2. VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel — optional Thai Som Kokoro voice (upstream Apache-2.0; Som dataset CC BY 4.0)
3. VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel — optional Thai Vachana voices (MIT model card, incomplete dataset rights audit)
4. VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel — NEW optional multilingual model (18 selectable voices, 7 languages, CPU ONNX INT8; Apache-2.0 model card, training and voice rights not independently audited)
5. VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel — optional experimental AI translation model. Requires separate Torch/Transformers/SentencePiece runtime; not included in core Portable. Previous semantic evaluation failed 2/3 cases; not recommended for unattended Live translation.
6. VoxWeaveTTS-TikTok-Extension-v0.2.5.zip — existing optional user-installed browser extension for TikTok Live comments, unchanged
7. SHA256SUMS-v0.8.0.txt — SHA-256 digests for all six distributed binaries/archives

The core ZIP intentionally ships **only MakHam Paradee weights**. Other heavy model weights are optional packages to avoid unnecessary download, and no private user settings, credentials, recorded audio or trained model caches are shipped.

## What's new

- One **โมเดลเสียงตามภาษา** tab configures an Engine and Voice per language. Assigned languages no longer appear in the add dropdown until removed; the Delete button is separated from its description.
- Independent **ปรับเสียง** section for every saved language, with precise Speed, Gain, Pitch, Bass, Treble, Formant and Seed, plus Save/Load/Refresh Voice Presets in the shared portable presets folder. Voice Preset loading changes audio tuning only, not language Engine/Voice assignment.
- **ใช้การเลือกโมเดลตามภาษา** is enabled per workspace under **กำหนดการอ่านข้อความและข้อมูลพิเศษ**. When disabled, or when the message language has no match, it uses that workspace's **Default Engine / Model** and voice/tuning.
- Kokoro-82M INT8 CPU provides English (US/UK), Spanish, French, Hindi, Italian, Japanese and Brazilian Portuguese voices. Native Chinese, Korean, German and Russian speech engines are not in this package. Script detection cannot distinguish all Latin-script languages; use explicit language or AI Translation target where needed.
- Install and remove optional TTS/AI model packages in UI, including uninstall for a legacy locally installed M2M100 model folder. The user must confirm removal; installed models are never deleted by this upgrade.
- Expanded AI Translation target options. Translation and speech synthesis remain independent.

## Install and run

1. Download and extract the portable ZIP **to any directory**. Do not run the EXE while it is still inside the archive.
2. Start **VoxWeaveTTS.exe** (graphical launcher) or **Start-Console.cmd** for diagnostic console. Open http://127.0.0.1:8765/ in Firefox or another browser.
3. From Settings, select **ติดตั้ง Model Package (.vwmodel)** and browse to a TTS package downloaded separately. Install only the voice packages you need.
4. For translation packages, use the AI Model Packages panel. M2M100 requires separate dependencies, and is not ready merely because its weight archive is installed.
5. In **โมเดลเสียงตามภาษา**, assign an Engine/Voice, expand **ปรับเสียง** and tune or load Voice Presets, then save.
6. In each relevant mode, open **กำหนดการอ่านข้อความและข้อมูลพิเศษ** and select **ใช้การเลือกโมเดลตามภาษา**. Set **Default Engine / Model** in the mode as a fallback.
7. The app is fully portable. New settings, caches, downloaded models and presets are created inside the extracted app folder; existing user data is **not** included in the Release ZIP.

## Runtime, licensing and limitations

- Python 3.11 and MakHam model are bundled. Additional Kokoro ONNX / eSpeak NG runtime and language dictionary data are bundled for the optional Kokoro model.
- The optional M2M100 package contains weights, not the large PyTorch runtime. Its language quality is experimental and previous tests were inadequate.
- CPU inference speed varies with available RAM and model; multi-language repeated inference can be memory intensive. No guarantee that all models can run simultaneously on low-memory machines.
- Speed and Gain are available with the built-in runtime. Nonzero Pitch/Bass/Treble DSP requires a separately installed FFmpeg build with Rubber Band support; this binary is **not** redistributed in the Portable ZIP, in line with the project license policy. The Formant checkbox affects Pitch DSP only when available.
- eSpeak NG runtime includes GPL-3.0 third-party licensing and source obligations (see THIRD_PARTY_NOTICES.txt, docs/third-party/ESPEAK_NG_GPL-3.0.txt and upstream https://github.com/espeak-ng/espeak-ng). Model assets include source/attribution/license in their .vwmodel manifests.
- License/attribution for each model, voice and training dataset needs review for the actual intended commercial use. The project does not independently certify all voice rights.
- YouTube Browser live mode is experimental and depends on provider behavior; TikTok Extension requires user installation; platform API permissions/quotas apply independently.
- Future work: voice cloning and model training, native voice emotions, word-level subtitle alignment and production evaluation across all language/model combinations.

## Verification checklist

- Main and optional package SHA256 hashes listed in SHA256SUMS-v0.8.0.txt.
- Main portable extracted runtime tested by invoking embedded Python and synthesizing MakHam audio.
- Kokoro optional model tested using embedded Python and model pack: voice synthesis on CPU.
- Previous optional Vachana and FastThaiG2P packages verified for manifest and embedded model checksums.
- Tests: Python unittest and Node.js UI smoke suites.
- No user configurations, API keys, personal voice assets, or local AI weights in the core ZIP.

See [Multilingual TTS guide](MULTILINGUAL_TTS_TH.md), [Commercial License Policy](COMMERCIAL_LICENSE_POLICY_TH.md), [Model Packaging](MODEL_PACKAGES_TH.md).
