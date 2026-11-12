# Roadmap

**Distribution gate:** Review [Commercial-First License Policy](COMMERCIAL_LICENSE_POLICY_TH.md) before adding model weights, pretrained voicepacks, training datasets, or bundling FFmpeg in portable releases. An MIT app license is not a commercial clearance for third-party assets.


For the full rationale, detailed tasks, dependencies and acceptance tests, see [Project Vision (Thai)](PROJECT_VISION_TH.md), [Development Plan (Thai)](DEVELOPMENT_PLAN_TH.md), and [Requirements (Thai)](REQUIREMENTS_TH.md).

**Status (v0.4.0):** Thai CPU WAV synthesis, a self-contained Windows portable executable, Web UI, source queues and browser-driven OBS subtitles are implemented. Voice cloning, model training, streaming TTS, hardware playback clocks and automatic word-level alignment remain planned.

## Milestone 0 — Foundation (in repository)
- [x] Project identity, public repository and MIT source license
- [x] Modular folder and privacy exclusions
- [x] Deterministic text replacement, masking, skip/silence and pronunciation mapping
- [x] Local-only HTTP preview API and web preview
- [x] Unit tests
- [x] Model-based Thai speech output (optional local CPU engines; not yet full-featured)

## Milestone 1 — Real speech generation (partial: CPU preview works)
- [x] Evaluate an initial Thai CPU ONNX TTS backend (FastThaiG2P), document source and licensing caveats
- [x] Define voice engine protocol and capability discovery for the installed fixed voice
- [x] Real 24kHz PCM16 WAV from Thai text via local API, plus exact silence from filtering rules
- [x] Web preview of synthesized WAV, basic speed control, private test samples on T:
- [x] Basic engine-neutral sequential speech generation queue, status events and cancellation (does not interrupt in-flight inference)
- [ ] Streaming playback, hard cancellation during inference and advanced queue policies
- [ ] Voice cloning / reference voice storage
- [x] Fixed ONNX per-job seed control and verified byte-identical repeats for the same Thai text/seed in CPU smoke tests
- [x] Bounded repeated-5 chat pattern (`555`, `55555`, etc.) with numerical-context exclusions and original Subtitle preservation
- [ ] Listening-based Thai pronunciation regression testing and native phoneme overrides
- [ ] Further engine quality/speed benchmarks and longer text stress tests

## Milestone 2 — Voice Studio / Long Text (partial)
- [x] Import .txt/.md via browser and engine-neutral API, basic Markdown narration cleanup, TXT/Markdown chapter detection and paged text chunks
- [x] Rules/Pronunciations JSON editor: pretty-format, validation, import/export, quick Unicode-safe entry, persistent local save/reload and stale-tab revision conflict checks
- [x] Preserve common Thai/Emoji Unicode sequences when cutting document chunks
- [x] Seven independent workspace views with one active audio/OBS owner and cross-tab SSE/revision checks
- [x] Shared global Engine/Voice/Speed/DSP persistent configuration; Seed, Presets and Rules remain central
- [x] Local Live/Discord text-input simulators with independent text and playback
- [x] Discord Client room selection via explicit Channel ID and approved-app Local RPC architecture; subscribed events filter by selected room
- [x] Discord Desktop RPC receive messages confirmed by the user with authorized consent in dev17; broader cross-machine provider validation is still pending
- [x] Official YouTube Live REST and Discord Bot REST read-only pollers with ephemeral credentials, dedupe, filters, bounded queues and opt-in sequential playback
- [ ] Verify actual providers using authorized accounts, add low-latency YouTube streamList/Discord Gateway and advanced moderation/queue priority
- [ ] Persist optional mode drafts and improve cross-mode job history without losing privacy
- [x] Prevent arbitrary splitting of Thai continuous words in Estimated Subtitle; use explicit separators or keep full generated Segment
- [x] Improve Document Reader fallback boundaries and expose uncertainty; version document IDs to avoid misapplied reading bookmarks
- [ ] Integrate a commercially-cleared Thai word tokenizer/linguistic segmenter for exceptionally long unspaced book paragraphs
- [x] Send selected chapter chunk through existing Rules/Pronunciations and Engine-independent Speech Queue
- [x] Private hash-keyed reading position and explicit resume/clear after reopening the document
- [x] Browser-managed per-chunk audio playback with pause/stop and optional next chunk after ended event (one synthesis at a time)
- [x] Browser HTMLMediaElement currentTime reporting, local OBS segment captions and pause/resume/seek/end
- [ ] Hardware audio-device clock, resilient streaming, word-level alignment and authenticated subtitle event stream

- [x] Select 2 real Thai CPU Engines and save/load local Voice Presets
- [x] Paired Slider/Numeric inputs for Native Speed and post-DSP Gain/Pitch/Bass/Treble, formant-preserve mode
- [ ] Native Formant shift, expressive style models and pause adjustment
- [ ] Distinguish model-native controls from post-processing DSP
- [ ] A/B audition, saved presets, non-destructive audio cache
- [ ] Novel/TXT/Markdown multi-chapter pipeline

## Milestone 3 — Shared Speech Coordinator / Live services (partial)
- [x] Engine-neutral Adapter Contract v1 and explicit Registry (ready for self-trained engines)
- [x] In-memory FIFO Audio Preparation Jobs, Dedup by source/message ID, bounded memory/TTL and Versioned Events
- [x] HTTP Job Queue, Status, Cancel, Events and WAV Download endpoints; UI queue preview
- [x] Browser Media Playback Clock from currentTime with Pause/Resume/Seek/End
- [ ] Native output-device playback clock and streaming player
- [ ] Durable queue/snapshot and reconnect semantics
- [ ] Nonblocking streaming, Backpressure and priority policies

- [ ] Local authenticated HTTP/WebSocket speech APIs
- [x] Sequential queue baseline
- [ ] Queue policies: latest, priority, manual, filtered
- [ ] Discord message intents and authorization
- [ ] YouTube Live Chat and video comment polling
- [ ] Per-source safety filtering and anti-spam policies

Read [Engine-Neutral Core](ENGINE_NEUTRAL_CORE_TH.md) for contract and current limitations.

## Milestone 4 — Subtitle coordination
- [x] Browser-reported Segment Timeline for live local Subtitle Preview
- [ ] Word/phoneme source-span alignment and audio-hardware output timing
- [x] Local transparent OBS Browser Source and in-memory GET /v1/playback/state snapshot
- [x] Local bounded SSE snapshot push + reconnect; OBS HTTP Polling fallback
- [x] Optional Unicode-grapheme caption windows with **estimated** internal segment timing
- [x] Lightweight PCM16 audio activity detection independent of TTS Engine, with silent-gap cue masking and pluggable AlignmentProvider
- [x] User-reviewed word/phrase timing editor, validated public-text offsets, local JSON export/import and in-memory cue revisions
- [x] Browser PCM16 Waveform Editor with responsive high-DPI peaks, zoom/pan, click-to-seek, time-range drag and keyboard nudge
- [ ] Real listener-reviewed Thai reference waveform/timecode corpus with consent and hash-based session binding
- [x] Reference timing evaluation metrics: coverage, mean/max boundary error, within-100ms
- [ ] True automatic word/syllable alignment from speech audio, and authenticated multi-client playback ownership
- [ ] Sentence/subsentence segments, optional word alignment
- [ ] Stream offset calibration, cancellation and multi-consumer validation

## Milestone 5 — Portable release
- [x] Windows EXE launcher and self-contained Python/ONNX CPU runtime, no external Python for MakHam Thai TTS
- [x] CPU-only MakHam Paradee inference and local cache/model paths tested in relocated portable folder; GPU support and further models remain future
- [ ] Test downloadable ZIP from an isolated extraction on Windows, publish hash and GitHub release; untouched clean-machine compatibility still requires external QA
- [ ] Third-party license and redistribution audit