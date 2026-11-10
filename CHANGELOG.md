# Changelog

All versions here describe development snapshots; no portable binary or GitHub Release is implied.

## 0.3.0.dev0 — Engine-neutral adapter registry and speech job queue (2026-11-10)

- Introduced explicit versioned, ML-independent EngineRegistry and PCM16 adapter protocol; future user-trained voice models can register without editing core text/HTTP/queue modules.
- Kept FastThaiG2P and MakHam Paradee via the shared registry; unverified commercial model rights remain `review_required`.
- Added bounded single-worker speech preparation queue: FIFO, source-message dedup, state transitions, cancellation, generic renderer injection and safe error handling.
- Added HTTP queue/status/event/audio/cancel endpoints and a simple browser queue preview.
- Explicitly separated generated audio segment offsets from live playback clock events (not implemented).
- Verified mock-adapter tests without any ML dependency and real queued audio synthesis through both installed Thai CPU engines.

## 0.2.0.dev5 — Retire experimental laughter-spelling UI (2026-11-10)

- Removed the dedicated "55555 laughter spelling" selector, test button, and associated frontend event handler on user request.
- Kept the general Rules/Pronunciations editor, `five_run` text replacement, subtitle preservation, both TTS Engines, DSP controls, and Voice Presets.
- Confirmed FastThaiG2P G2P maps `5`, `๕`, `ห้า`, and `ฮ่า` to the same IPA; the isolated-phoneme speech failure cannot be solved by swapping these spellings alone. `ฮ่าร้อย` gives the same first phoneme with extra context, but should not be substituted automatically because its ending remains audible.
- Recorded user's observation that MakHam Paradee produces more recognizable laughter with a trailing s-like sound while FastThaiG2P still mispronounces isolated laughter.

## 0.2.0.dev4 — Two Thai Engines and detailed Voice Studio (2026-11-10)

- Added MakHam Paradee 8.46 MB INT8 CPU ONNX as a second working Thai TTS Engine, alongside FastThaiG2P.
- Introduced explicit Engine/Voice discovery and an Engine selector in Web UI and API; unavailable models are not presented as ready.
- Added paired Slider + Numeric controls for Native Speed and real post-DSP Gain, Pitch, Bass and Treble; optional formant preservation during Pitch shifts (no arbitrary formant shift).
- Added private save/load Voice Presets with validated settings in portable `data/presets/`.
- Added optional FFmpeg/Rubber Band DSP with safe bounded parameters, plus a project-local MakHam asset preparation step.
- Tested CPU WAV synthesis through both Engines and HTTP API with non-default voice controls; no audio assets or voice samples added to public Git.
- Documented Voice Cloning and Fine-tuning as future work, not completed functionality.

## 0.2.0.dev3 — Clarify Seed and add TTS pronunciation audition (2026-11-10)

- Verified via CPU waveform analysis that changing ONNX Seed produces highly correlated PCM audio; different hashes alone do not imply perceptibly different voice or corrected pronunciation.
- Moved Seed controls to Advanced and clarified that Seed is for reproducibility, not speaker timbre, pitch, or pronunciation tuning.
- Added a laughter TTS spelling selector and an audition action that updates only the `five_run` replacement's spoken side; the original `55555` display remains unchanged.
- No prerecorded laughter clips or new voice models. Thai phonetic accuracy still needs user listening evaluation.

## 0.2.0.dev2 — Repeated-5 chat pronunciation pattern (2026-11-10)

- Added `match_mode=five_run` for rules that convert any run of 3+ ASCII 5s (e.g. `555`, `55555`, `5555555`) to user-defined spoken text while keeping the exact original subtitle and source span.
- Excluded digit sequences inside numbers or decimal/grouped numeric strings; retained literal matching as the default for all existing rules.
- Updated Thai UI example and regression tests. The speech remains synthesized by the TTS engine using the selected ONNX seed; no prerecorded laughter is used.

## 0.2.0.dev1 — Deterministic ONNX seed control (2026-11-10)

- Investigated unstable output for `ฮ่า ฮ่า ฮ่า` (sometimes perceived as `พาน พ่าน พ่าน`). G2P produced the same phonemes but ONNX model samples varied across repeated calls.
- Added per-job ONNX session creation and controlled seed to obtain reproducible WAV for the same input/speed/seed on the tested CPU runtime; user can audition different seeds from Web UI.
- Persist selected seed inside private portable `data/settings/synthesis.json` using `GET/POST /v1/settings/synthesis` with input validation.
- Retained the original pure TTS replacement rule `55555` -> `ฮ่า ฮ่า ฮ่า`. No laughter audio clip system, no uploaded effects or audio-file substitution.
- Added deterministic-seed unit tests and real-model regression script. Pronunciation accuracy still requires listening evaluation.

## 0.2.0.dev0 — M1 Thai CPU WAV preview (2026-11-10)

- Implemented optional local PyThaiTTS/FastThaiG2P CPU ONNX voice adapter with a fixed `thai_som` voice.
- Implemented `POST /v1/speech` (PCM16 mono 24 kHz WAV), `GET /v1/engines` and `GET /v1/voices`.
- Implemented real PCM silence segments, matched to replacement and skip rules.
- Added local browser audio preview, playback/download controls and speed setting.
- Added project-local environment/model installation script, API smoke test and documentation in Thai.
- Voice cloning, pitch/formant/expressivity and streaming subtitle events remain unimplemented.
- Tested actual WAV synthesis and the 400ms silence case on Windows 10 CPU.

## 0.1.0 — Foundation (2026-11-10)

- Created public repository, MIT source license, text processing API, dictionaries and filters.
- Added initial UI, unit tests, CI, architecture, requirements and full Thai development plan.