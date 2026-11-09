# Roadmap

For the full rationale, detailed tasks, dependencies and acceptance tests, see [Project Vision (Thai)](PROJECT_VISION_TH.md), [Development Plan (Thai)](DEVELOPMENT_PLAN_TH.md), and [Requirements (Thai)](REQUIREMENTS_TH.md).

**This is a proposed plan:** unchecked items are not implemented. The foundation only processes text; voice/audio streaming and Windows portable EXEs are future milestones.

## Milestone 0 — Foundation (in repository)
- [x] Project identity, public repository and MIT source license
- [x] Modular folder and privacy exclusions
- [x] Deterministic text replacement, masking, skip/silence and pronunciation mapping
- [x] Local-only HTTP preview API and web preview
- [x] Unit tests
- [ ] Model-based speech output

## Milestone 1 — Real speech generation
- [ ] Evaluate Thai TTS engines, licenses and offline constraints
- [ ] Voice engine adapter interface and capability discovery
- [ ] Stream-capable playback and cancellation
- [ ] Local reference voice/profile storage
- [ ] Real speech testing in Thai with pronunciation regressions

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