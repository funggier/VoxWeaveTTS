# Roadmap

For the full rationale, detailed tasks, dependencies and acceptance tests, see [Project Vision (Thai)](PROJECT_VISION_TH.md), [Development Plan (Thai)](DEVELOPMENT_PLAN_TH.md), and [Requirements (Thai)](REQUIREMENTS_TH.md).

**Status:** The initial foundation processes text; M1 has a working fixed-voice Thai CPU WAV preview. Voice cloning, live audio streaming, synced subtitle events and Windows portable EXEs remain planned; unchecked items are not implemented.

## Milestone 0 — Foundation (in repository)
- [x] Project identity, public repository and MIT source license
- [x] Modular folder and privacy exclusions
- [x] Deterministic text replacement, masking, skip/silence and pronunciation mapping
- [x] Local-only HTTP preview API and web preview
- [x] Unit tests
- [ ] Model-based speech output

## Milestone 1 — Real speech generation (partial: CPU preview works)
- [x] Evaluate an initial Thai CPU ONNX TTS backend (FastThaiG2P), document source and licensing caveats
- [x] Define voice engine protocol and capability discovery for the installed fixed voice
- [x] Real 24kHz PCM16 WAV from Thai text via local API, plus exact silence from filtering rules
- [x] Web preview of synthesized WAV, basic speed control, private test samples on T:
- [ ] Streaming playback, explicit cancellation and queue policy
- [ ] Voice cloning / reference voice storage
- [x] Fixed ONNX per-job seed control and verified byte-identical repeats for the same Thai text/seed in CPU smoke tests
- [ ] Listening-based Thai pronunciation regression testing and native phoneme overrides
- [ ] Further engine quality/speed benchmarks and longer text stress tests

## Milestone 2 — Voice Studio
- [ ] Speed, pitch, formant, EQ/brightness, expressivity and pause adjustment
- [ ] Distinguish model-native controls from post-processing DSP
- [ ] A/B audition, saved presets, non-destructive audio cache
- [ ] Novel/TXT/Markdown multi-chapter pipeline

## Milestone 3 — Live services
- [ ] Local authenticated HTTP/WebSocket speech APIs
- [ ] Queue policies: sequential, latest, priority, manual, filtered
- [ ] Discord message intents and authorization
- [ ] YouTube Live Chat and video comment polling
- [ ] Per-source safety filtering and anti-spam policies

## Milestone 4 — Subtitle coordination
- [ ] Playback-clock-led speech events and source-span mapping
- [ ] OBS transparent browser overlay and reconnect snapshot
- [ ] Sentence/subsentence segments, optional word alignment
- [ ] Stream offset calibration, cancellation and multi-consumer validation

## Milestone 5 — Portable release
- [ ] Windows executable and runtime bundling, no external Python
- [ ] GPU/CPU fallback verification, model portability and local caches
- [ ] Clean Windows extraction test, ZIP, hashes and GitHub release
- [ ] Third-party license and redistribution audit