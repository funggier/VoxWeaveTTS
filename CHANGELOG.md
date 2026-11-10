# Changelog

All versions here describe development snapshots; no portable binary or GitHub Release is implied.

## 0.3.0.dev8 — Browser PCM16 Waveform Editor for Manual Alignment (2026-11-10)

- Added independent web/waveform_editor.js: parses generated PCM16 RIFF/WAVE (mono/stereo 8–96kHz), builds a bounded 256-frame peak envelope and draws a HiDPI-aware waveform with speech/silence regions, local manual cue spans, selection marks and player position. No extra model, library, cloud calls or disk persistence.
- Added zoom (1–32×), horizontal pan, click-to-seek, drag-to-set Start/End milliseconds and keyboard audio seeking (25ms, Shift 5ms). Waveform edits only the form until the user explicitly saves manual cues to a ready Speech Job.
- Integrated the waveform with the existing in-memory manual cue/revision workflow and served its static JS from the loopback HTTP server. Unsupported WAV formats leave the original numeric/manual timecode editor usable.
- Added synthetic PCM16 waveform interaction smoke tests, integrated manual editor smoke checks and HTTP asset tests. Real Thai audio cue recognition remains absent; no automatic word-level forced alignment is claimed.
- Added instructions for building a rights-cleared, listener-reviewed Thai boundary benchmark; no accuracy data is fabricated.

## 0.3.0.dev7 — User-reviewed manual subtitle alignment and timing evaluation (2026-11-10)

- Added a model-neutral Manual Alignment Workbench: select a span of filtered display text, mark its start/end from the Browser's WAV currentTime, and edit/import/export bounded JSON timecodes. No external models, weights, or cloud services.
- Added POST /v1/jobs/{speech_id}/alignment with strict segment, Unicode, non-overlap and privacy validation plus optimistic per-job revisions; cues remain in memory until job expiry and are not automatically persisted.
- Added local OBS ?mode=manual and SSE support. Unannotated time ranges remain blank; the mode is labeled manual_user_timed, NOT machine word-aligned.
- Added POST /v1/alignment/evaluate for exact-span reference coverage and boundary MAE/max/within-100ms metrics; absent matched references return null errors rather than fabricated accuracy.
- Added Python API/model-neutral regression tests and Node UI smoke tests including surrogate-pair emoji offsets.
- Real automatic Thai word/syllable Forced Alignment remains unimplemented, pending commercial-clear model and reference corpus evaluation.

## 0.3.0.dev6 — Model-free PCM Audio Activity Alignment (2026-11-10)

- Added a pluggable engine-neutral AudioAlignmentProvider contract and built-in stdlib PCM16 energy activity analyzer (20ms RMS windows, thresholding, noise floor, short-gap merging); no pretrained weights or new dependencies.
- Speech Coordinator now annotates ready-job audio segment metadata with bounded speech-like energy intervals; analysis errors do not fail successful WAV synthesis.
- Added third local OBS caption mode, /overlay?mode=activity, which hides captions over detected silent regions within generated speech segments without claiming real word-level forced alignment.
- Activity metadata is allowlisted/validated through the public queue timeline and PlaybackState; no original private text or spoken replacement payload is published.
- Added Python signal-based, negative, privacy, provider and playback tests. Precise Thai word/syllable audio alignment remains future work subject to commercial licensing review.

## 0.3.0.dev5 — Low-latency local SSE subtitles and estimated caption windows (2026-11-10)

- Added a bounded local Server-Sent Events (SSE) transport at GET /v1/playback/stream; it sends initial and changed playback snapshots, has 8-client capacity, heartbeats, stale-caption transitions and auto-reconnect after 20s. Existing GET /v1/playback/state remains as fallback.
- OBS Overlay now uses EventSource first and HTTP polling only as fallback, reducing additional overlay transport delay compared with 250ms polling.
- Added opt-in /overlay?mode=estimated: Unicode grapheme-safe subtitle windows interpolated WITHIN a generated speech segment. This is explicitly approximate text timing, NOT actual word/syllable/phoneme audio alignment.
- Added versioned stream state revisions, reconnect handling, stale-browser caption hiding, API/SSE tests and browser overlay simulator tests including Thai/emoji and markup-safe display.
- Retained model-neutral dependencies, locally bound API, original-word masking and commercial licensing restrictions.

## 0.3.0.dev4 — Browser media-clock subtitles and local OBS overlay (2026-11-10)

- Added an Engine-neutral PlaybackState relay with session IDs, increasing event sequences, ready-job timeline checks, safe silent segments and stale caption hiding.
- Added GET /v1/playback/state, POST /v1/playback/event (intent header), transparent GET /overlay and a shared Browser media-clock reporter.
- Document Reader and queued WAV browser players report currentTime during Play/Pause/Resume/Seek/End so OBS subtitle segments follow playback rather than model-generation completion.
- Added Python service/API tests and Node media-clock regression tests; this is segment-level timing from HTMLMediaElement, not word alignment or a hardware audio clock.
- Retains local-only API, private text masking and Commercial-First licensing rules.

## 0.3.0.dev3 — Resumable, sequential document reading (2026-11-10)

- Added private, engine-independent reading bookmarks keyed by the normalized document SHA-256; stores only chunk size, total, next unread chunk and timestamp. No novel text, path or user audio is persisted.
- Added GET/POST /v1/reading/progress and POST /v1/reading/progress/clear with atomic local data writes, optimistic revisions, bounded storage, explicit mutation intent headers and stale-tab conflict responses.
- Browser Reader can save the selected position, restore a matching position after re-opening TXT/Markdown, clear it, synthesize/play a selected chunk, pause/resume, stop and optionally advance one chunk after browser audio 'ended'.
- Bookmarks advance ONLY after playback finished; stopping or audio-generation failure does not skip unfinished text. At most one document chunk is synthesized at a time; no full-book preload, remote player event timing or OBS sync.
- Added model-free HTTP/validation/concurrency/bookmark tests and Node browser flow smoke for resumable playback and end-of-document behavior.

## 0.3.0.dev2 — Persistent Rules/Pronunciations editor (2026-11-10)

- Added atomic, validated on-disk Rules and Pronunciations storage in the existing ignored portable data paths, with section-specific SHA-256 optimistic revision checks to avoid overwriting edits made in another tab.
- Added GET/POST /v1/settings/text for safe configuration loading and saving, while retaining existing GET /v1/rules, GET /v1/pronunciations and request-specific overrides for all Engines.
- Added browser actions to save in program, load saved settings, import exported JSON files, and restore saved settings at startup without overwriting unsaved edits or installing any model.
- Added Python HTTP/persistence/conflict/legacy migration tests plus dependency-free Node browser editor interaction smoke test.
- Preserved Commercial-First distribution policy; local user rules and files remain outside GitHub.

## 0.3.0.dev1 — Engine-neutral TXT/Markdown narrator input (2026-11-10)

- Added Python standard-library Document Reader with Thai TXT chapter detection, Markdown heading parsing, narrated-text cleanup and safe text chunking (100–450 characters, paging and normalized offsets).
- Improved existing Rules/Pronunciations JSON editors with pretty-format, syntax/type checks, local download and quick-entry forms that safely encode quotes, backslashes, Thai Unicode and emoji.
- Improved document chunk boundaries to avoid splitting common emoji ZWJ/skin-tone/regional-indicator sequences, and added special character regression tests.
- Added POST /v1/documents/preview using a separately bounded request size so document preview does not weaken small TTS API limits; imported files are not written to the server or repository.
- Web UI reads local UTF-8/Thai Windows-874 .txt/.md files, displays chapters/chunks, and can copy the chosen chunk to the text editor or send it to the existing engine-neutral Speech Queue with current rules and voice settings.
- Added document normalization, stable pagination, validation, sanitization and mock-engine queue regression tests; maintained existing real Thai Engine APIs.
- No unattended full-book audio generation, saved reading progress, Playback Clock, or voice training is claimed.

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