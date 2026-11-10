# Architecture and design invariants

## Data flow

InputAdapters (Novel/Markdown, Discord, YouTube, external)
→ Moderation/Filtering + Queue
→ Text Filter & Replacement
→ Thai Pronunciation/G2P (spoken side only)
→ Speech Plan {speech, silence, replacement segments}
→ Voice Engine Adapter (model-specific capabilities)
→ Playback Coordinator (actual output clock)
→ Audio Output and Speech Events
→ Subtitle Overlay / Event API / Consumers

## Local Subtitle Stream v1 (implemented preview)

The shared `PlaybackState` now maintains a per-process monotonically increasing revision and condition-variable notifications. The `GET /v1/playback/stream` SSE transport pushes the latest snapshot when reports change rather than polling; it is bounded to 8 subscribers, self-closes after 20 seconds, and preserves a REST polling fallback. No persistent event log or replay is maintained, and connection to a different machine is not exposed.

An independent `subtitle_cues.py` provides opt-in estimated Unicode grapheme windows inside generated speech segments. Estimated mode does **not** infer actual speech phoneme/word boundaries; generated-segment mode is the default. The Audio Browser clock continues to be authoritative for the **reported playback position**. See [Playback/OBS Guide](PLAYBACK_OVERLAY_TH.md).

## Browser Playback State and Local OBS Subtitles (implemented preview)

The Player HTMLMediaElement.currentTime (not model-completion time) is reported via web/playback_clock.js to src/voxweavetts/playback_state.py. The service validates and relays only the ready-job DISPLAY segments with monotonically increasing sequences and stale-caption expiry. GET /v1/playback/state feeds a transparent GET /overlay Browser Source. Pause/end/stop hide the subtitle. Missing: word-level forced alignment, direct OS audio clock, secure remote/LAN event stream. See [Playback/OBS](PLAYBACK_OVERLAY_TH.md).

## Private engine-neutral reading progress (implemented)

`reading_progress.py` persists only document SHA-256 keys, chunk configuration, next unread chunk and timestamp through atomic writes and per-document optimistic revisions; content and raw text stay in the browser and in ephemeral Speech Jobs, not in the reading progress file. The browser's audio 'ended' event advances the next-chunk position and optionally submits exactly one next chunk through the current queue. This is **not** a synchronized external player clock or OBS event bus.

## Engine-neutral persistent text settings (implemented)

`text_settings.py` owns validated portable Rules/Pronunciations state with atomic file replacement and per-section revision hashes; its HTTP API and browser editing controls do not depend on TTS models. These settings are used as defaults for any Engine through the existing shared text-processing layer, while explicit request overrides remain supported. File paths are fixed inside Git-ignored data directories. See [JSON Settings](PRONUNCIATION_JSON_TH.md).

## Engine-neutral TXT/Markdown Input (implemented)

The engine-independent Document Reader in src/voxweavetts/document_reader.py parses TXT/Markdown into chapter-indexed text chunks with normalized offsets and deterministic paging; the browser reads files locally, sends UTF-8 text through POST /v1/documents/preview, and lets the user push **only a selected chunk** through the existing Text Processor and Speech Queue. It never imports model modules or stores novel text on the server. See [Document Reader](DOCUMENT_READER_TH.md).

## Engine-neutral Core v1 (implemented)

The model-independent code is now in `src/voxweavetts/engine_contract.py` (Adapter Version 1, explicit Engine Registry, commercial review status) and `src/voxweavetts/speech_coordinator.py` (bounded in-memory sequential preparation queue, deduplication, cancellation, versioned events). Both depend only on the Python standard library; the current Thai model adapters remain behind a factory in `speech.py`. The HTTP `/v1/jobs` endpoints share the Text Plan and Voice Studio controls with `/v1/speech`. State `ready` means **WAV generation completed**, not that audio was played. See [Engine-Neutral Core](ENGINE_NEUTRAL_CORE_TH.md).

## Core separation

- The original message and the display text are different concepts.
- Spoken/pronunciation hints never automatically overwrite display text.
- Replacement actions define speech and display independently.
- Silence is an explicit segment with duration; never rely on TTS interpreting whitespace.
- Voice profile/pitch/formant/speed controls require engine capability negotiation.
- Subtitle timing is relative to the **actual playback clock**, not model-generation completion.
- Word highlighting requires genuine word timings or forced alignment, not fake estimates.
- The overlay gets sanitized display data; do not publish filtered original content.
- Messages must have durable unique IDs, source IDs and queue order for dedup/reconnect.
- A lost browser overlay can reconnect and request a playback snapshot.
- Real-time stream connectors and TTS engines must never share authentication secrets.
- Local user data/models/reference audio are outside Git and package outputs.

## Current implemented slice (M1 / Voice Studio preview)

The stdlib text pipeline (`src/voxweavetts/processing.py`) performs literal longest-match replacement and explicit silence segmentation, then applies pronunciation hints on the spoken side only. **Optional** `src/voxweavetts/speech.py` supports two CPU ONNX engines (FastThaiG2P/Kokoro Thai and MakHam Paradee) to render real 24kHz PCM16 WAV with explicit silence samples. The localhost HTTP API offers `POST /v1/speech`, `GET /v1/engines` and `GET /v1/voices`, and the web tester can play the WAV. Each engine uses its own fixed voice (`thai_som` or `paradee_thai`) and native speed. The Voice Studio includes paired Slider/Numeric controls, optional post-DSP Pitch/Balance/EQ via FFmpeg, pure Python Gain and local private presets. No voice cloning or training is implemented. The Speech Coordinator, playback-clock events, voice cloning, streaming and overlay are not yet implemented.

**Known limitation:** literal substring matching is not full Thai morphological segmentation. Future matching strategies should use tokenization/phrase boundaries and optional safe patterns, with robust tests against substrings and Unicode edge cases.

## Planned implementation boundaries

- `VoiceEngine`: pluggable, local-first; optional backends for Thai voice cloning and installed system voices.
- `VoiceStudio`: the current UI includes Engine selection, numeric/sliders, and local presets; voice profile authoring, native expressive controls and A/B comparison remain planned.
- `SpeechCoordinator`: current core handles FIFO audio preparation, dedup, cancellation and bounded RAM; future playback clock, persistent jobs, priority and streaming remain planned.
- `Events`: versioned WebSocket event stream and reconnect snapshots.
- `LiveConnectors`: separately configured Discord and YouTube adapters with OAuth/bot tokens never in public repo.
- `PortableBuilder`: deterministic Windows build that bundles runtime; model packs kept separate subject to licensing.

Live Input Adapters and a hardware audio-device playback clock are not yet implemented; the local Browser-reported media clock and OBS overlay preview are available. See [VOICE_STUDIO_TH.md](VOICE_STUDIO_TH.md) and [VOICE_TRAINING_TH.md](VOICE_TRAINING_TH.md).