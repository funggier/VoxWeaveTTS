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
- `SpeechCoordinator`: queue, cancellation, accurate segments, backpressure.
- `Events`: versioned WebSocket event stream and reconnect snapshots.
- `LiveConnectors`: separately configured Discord and YouTube adapters with OAuth/bot tokens never in public repo.
- `PortableBuilder`: deterministic Windows build that bundles runtime; model packs kept separate subject to licensing.

The live Input Adapters and actual playback-clock timing are not yet implemented. See [VOICE_STUDIO_TH.md](VOICE_STUDIO_TH.md) and [VOICE_TRAINING_TH.md](VOICE_TRAINING_TH.md).