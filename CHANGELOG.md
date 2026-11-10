# Changelog

All versions here describe development snapshots; no portable binary or GitHub Release is implied.

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