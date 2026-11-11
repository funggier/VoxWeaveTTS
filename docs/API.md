# API Contract — Engine-Neutral Document Reader preview (v0.3.0.dev9)

Loopback base: `http://127.0.0.1:8765`. JSON UTF-8. Maximum request body currently 64 KiB; maximum text is 8,000 characters.

## Implemented

`GET /v1/status` — version and exact feature availability (models present + Python dependencies present).

`GET /v1/rules` — the current local `data/filters/rules.json` if present, or an empty list.

`GET /v1/pronunciations` — the current local `data/dictionaries/pronunciations.json` if present, or an empty map.

`POST /v1/text/process`:
```json
{
  "text": "เขาเป็นอมตะและพบคำต้องห้าม",
  "source": "manual",
  "rules": [{"match":"คำต้องห้าม","mode":"silence","silence_ms":400,"display":"***"}],
  "pronunciations": {"อมตะ":"อะ มะ ตะ"}
}
```
The optional `rules` and `pronunciations` override local file configuration for this request only. Response fields: `display_text`, `spoken_text` (speech-only linear text), `segments` (`kind`, `spoken_text`, `display_text`, `silence_ms`, source offsets), `source`. This is a preview of a future speech plan, NOT synthesized audio.

Rules:
- `mode=replace`: `spoken` optional, `display` optional (default original spelling).
- Optional `match_mode`: `literal` (default) or `five_run` (requires `match="555"`). A `five_run` rule matches three or more consecutive ASCII 5 characters outside surrounding numbers. `55555` → a selected replacement such as `ฮ่า ฮ่า ฮ่า`, while its actual display remains `55555` unless `display` is set. Grouped numbers or decimals such as `5,55555` and `55555.50` are excluded. This is a predefined safe pattern, not user-supplied regex.
- `mode=silence`: `silence_ms` 0–10,000; `display` defaults to ***.
- `mode=skip`: removes speech time, `display` defaults to ***.
- Optional `sources` list restricts application to specific source IDs.
- Longest literal match at the earliest position wins; input order breaks exact ties.

## Real audio endpoint (M1 preview)

`GET /v1/engines` — two Thai CPU ONNX adapters (`fastthaig2p-cpu`, `makham-paradee-cpu`) with model readiness, voice IDs, supported flags, and a `control_schema` object including slider/min/max/step defaults and `ffmpeg_ready`.

`GET /v1/voices` — fixed `thai_som` and `paradee_thai` with `engine_id`, `ready` and `voice_cloning=false`.

`POST /v1/speech` — uses the **same** text, rules, pronunciations and source fields as `POST /v1/text/process`, plus `engine_id: "fastthaig2p-cpu"` / `"makham-paradee-cpu"`, corresponding `voice_id` (`"thai_som"` / `"paradee_thai"`), `speed: 1.0` (range 0.6–1.5), optional `voice_controls` and `seed` (integer 0–2147483647). Returns `audio/wav` (24 kHz mono PCM16), `X-VoxWeaveTTS-Duration-Ms` and `X-VoxWeaveTTS-Seed` headers. Text input may be at most 8000 chars for text processing but total spoken segments are limited to **500 spoken characters and 50 segments** per audio request. CPU TTS assets are optional: if unavailable, the endpoint responds `503`. Unsupported control/engine/voice returns `400`.

This endpoint **generates audio, not timed playback events**; its segment duration metadata is not a live subtitle timeline. See [M1_AUDIO_TH.md](M1_AUDIO_TH.md).

## Synthesis settings and reproducibility (implemented)

`GET /v1/settings/synthesis` returns `{"seed":100}` by default or the saved seed in `data/settings/synthesis.json`.

`POST /v1/settings/synthesis` requires `Content-Type: application/json`, `X-VoxWeaveTTS-Intent: save-synthesis-settings`, and JSON body `{"seed":123}`. Stores only this validated integer under the portable project root. `POST /v1/speech` uses the saved seed when not supplied in the request, and a request-specific seed takes precedence.

FastThaiG2P uses stochastic ONNX operations. To ensure a fixed seed reproduces byte-identical WAV on the tested CPU runtime, `render_wav` seeds ONNX **before creating a new model session for each speech job**. Reusing a model session while merely reseeding the global runtime is not reproducible. This incurs extra model-initialization overhead; M1 prioritizes correctness over streaming latency. It **does not guarantee correct pronunciation**, only reproducibility for the same model/runtime/input. Waveform correlation between Seed 100/101 was measured at about 0.986 for `ฮ่า ฮ่า ฮ่า` and 0.997 for a longer Thai sentence; Seed does not select a different voice or provide useful timbre control.

## Voice Studio controls and presets (implemented in preview)

`POST /v1/speech` accepts `voice_controls`: `gain_db` (-18..+12 dB), `pitch_semitones` (-4..+4), `bass_db`/ `treble_db` (-12..+12 dB) and `formant_preserve` (boolean). Defaults are zero and `true` for formant preservation. Gain is handled by Python DSP, Pitch/EQ use **optional external FFmpeg with Rubber Band**. The Engine does not natively support Pitch/Formant/Emotion; independent formant shifting is unsupported. Silent segments remain exact PCM zeros.

`GET /v1/presets` lists local JSON presets. `POST /v1/presets` requires `X-VoxWeaveTTS-Intent: save-voice-preset` with JSON body containing `name`, `engine_id`, `voice_id`, `speed`, `seed`, and `voice_controls`. Up to 32 validated presets are saved locally in `data/presets/voice-presets.json`, which is Git-ignored. See [VOICE_STUDIO_TH.md](VOICE_STUDIO_TH.md).

## Persistent Rules and Pronunciations settings (implemented)

`GET /v1/settings/text` returns `{schema_version:1, rules:[], pronunciations:{}, revisions:{rules:<SHA256>, pronunciations:<SHA256>}, saved:{rules:boolean, pronunciations:boolean}}`. Old wrapped `data/filters/rules.json` (`{rules:[...]}`) is recognized for compatibility.

`POST /v1/settings/text` requires `Content-Type: application/json` and `X-VoxWeaveTTS-Intent: save-text-settings`. Body: `{section:"rules"|"pronunciations", value:[], expected_revision:"64-lowercase-hex"}`; the `value` must match the selected section type. Saving is atomic, validates all rule constraints and bounded file size, and rejects a stale revision with HTTP `409` without overwriting the file. Successful response includes updated revision. Rules are stored privately in `data/filters/rules.json`; pronunciation map in `data/dictionaries/pronunciations.json` (both Git-ignored). Corrupt existing files are NOT silently overwritten. No user-defined file paths or arbitrary Regex/Code execution are accepted.

`GET /v1/rules` and `GET /v1/pronunciations` remain supported, and `POST /v1/text/process`, `/v1/speech` and `/v1/jobs` use these saved settings when their request omits the corresponding field. A request-specific field still overrides saved values (including an explicit empty list or map).

## Rules and Pronunciations JSON editor

The existing browser-side JSON editors support pretty-printing (preserving Rule order), JSON syntax/top-level-shape validation, safe quick-entry of arbitrary Unicode/quoted/backslash-containing literal text, local JSON import/export, and explicit persistent server save/reload. Rules must remain a JSON array and Pronunciations a JSON object. The text API performs complete rule validation during processing; formatting alone is not a semantic rule validator. See [Thai JSON setup](PRONUNCIATION_JSON_TH.md).

## Discord Desktop Client RPC Room Reader (v0.3.0.dev12)

New workspace mode is discord_client. POST /v1/modes/activate with mode discord_client establishes exclusive playback ownership. POST /v1/sources/start for this mode requires source_id equal to a selected Discord text Channel ID (16–22 digit Snowflake) and credential object with client_id, client_secret, redirect_uri. Existing source stop/drain/status endpoints and intent headers remain unchanged.

The adapter connects to the official Discord Desktop IPC, requests user authorization for rpc and messages.read, exchanges the returned code with Discord OAuth, authenticates and issues SUBSCRIBE for MESSAGE_CREATE with args.channel_id equal to the selected room. Each dispatch is filtered again by channel_id. Other channels never enter the TTS queue; no old messages or edit events are requested.

The account connection remains subject to Discord's RPC app/tester approval and is unverified with real account credentials. GET /v1/sources/status?mode=discord_client and source drain status expose safe connection_phase and terminal failed_phase values. OAuth token exchange errors display only an allowlisted OAuth error identifier and HTTP status; they never return token, authorization code, Client Secret or raw Discord error descriptions. See [Discord Client Reader](DISCORD_CLIENT_READER_TH.md).

## Read-only YouTube / Discord Source Inputs (v0.3.0.dev11)

- POST /v1/sources/start: JSON {mode:"live"|"discord",mode_token,source_id,credential,filters:{blocked_words,max_chars}} with X-VoxWeaveTTS-Intent: start-live-source. Credential optional if VOXWEAVE_YOUTUBE_API_KEY / VOXWEAVE_DISCORD_BOT_TOKEN set in the server environment. Current owner required; credentials never returned or persisted.
- GET /v1/sources/status?mode=live|discord: read-only state/stats; no secrets.
- POST /v1/sources/drain: JSON {mode,mode_token,limit:1..20}, X-VoxWeaveTTS-Intent: drain-live-source. Returns bounded messages and status only for active owner.
- POST /v1/sources/stop: JSON {mode,mode_token}, X-VoxWeaveTTS-Intent: stop-live-source. Clears the source queue; switching workspace stops source automatically.
- All source POST requests require Content-Type: application/json. Auth/ownership failures return HTTP 409; invalid fields return HTTP 400; missing intent 403; wrong content type 415.
- YouTube first page establishes baseline and is not read. Subsequent pages use API nextPageToken/pollingIntervalMillis and require an API Key; Discord uses a Bot Token to poll Channel Messages after the latest Snowflake ID, obeying route rate-limit headers. Auto-read defaults ON after an explicit source connection but can be switched off in the UI. No back-channel publishing or data persistence.

See [Live Input Adapters](LIVE_INPUT_ADAPTERS_TH.md). Adapters are mocked-tested; external account test not yet completed.

## Independent Workspaces and Shared Voice Settings (v0.3.0.dev11)

- GET /v1/modes/state — active_mode, revision, exclusive_playback and supported mode IDs (no owner token).
- POST /v1/modes/activate — requires JSON {"mode":"studio|reader|queue|live|discord|rules|settings"} and X-VoxWeaveTTS-Intent: activate-mode; atomically invalidates the previous playback session/OBS state and returns the new owner mode_token plus revision.
- GET /v1/modes/stream — read-only bounded local SSE event=workspace for near-immediate cross-tab mode changes. It never includes owner tokens. Browser BroadcastChannel and HTTP polling are fallbacks.
- POST /v1/playback/event — after workspace activation, must include mode and mode_token from the current activation. Old mode/session reports return HTTP 409 and cannot repopulate OBS captions. Pre-workspace API consumers without activation remain compatible in isolated tests.
- GET /v1/settings/global-voice — returns revision and settings (or null) for shared Engine/Voice/Speed/DSP defaults.
- POST /v1/settings/global-voice — JSON {engine_id,voice_id,speed,voice_controls,expected_revision}, X-VoxWeaveTTS-Intent: save-global-voice. Validated, atomically saved in local gitignored data/settings/global-voice.json; stale revision returns 409.
- Studio, Reader, Queue, Live simulation and Discord simulation use the same Speech Coordinator and single OBS Overlay. Live/Discord have NO external platform adapters yet and accept only user-provided test text.
- Switching modes stops Browser output and prevents delayed autoplay, but does not guarantee interruption of in-progress CPU model inference.

See [Workspace Guide](WORKSPACE_MODES_TH.md).

## Thai-safe Caption/Document Boundaries (v0.3.0.dev9)

Estimated subtitle timing no longer cuts every ~22 Unicode graphemes: it selects explicit whitespace/punctuation separators in the filtered speech display text. Where the Thai text is continuous with no reliable break, the generated Speech Segment remains a single caption. No new API or external tokenizer is required.

POST /v1/documents/preview now includes `chunker_revision=thai_boundary_v2` and adds `boundary_quality` / `start_boundary_quality` for each Chunk. Possible values are `whitespace`, `punctuation`, `end_of_chapter`, `thai_preposed_vowel_hint`, `unicode_only_fallback` (plus `chapter_start` for the first Chunk start). The last two are heuristic/unavoidable hard-limit fallbacks, not dictionary word segmentation. `document_id` includes the new chunker revision in its SHA-256 input, invalidating old positional reading bookmarks safely; old records remain on disk and must be saved again at the correct Chunk.

## Browser Waveform Asset (implemented preview)

GET /waveform_editor.js returns the standalone, no-dependency PCM16 RIFF/WAVE Browser waveform viewer with Cache-Control: no-store. The viewer fetches already-ready WAV bytes from the existing GET /v1/jobs/{speech_id}/audio and renders a local peak envelope (no new waveform endpoint or server-side audio processing). Clicking/dragging changes Player position and the local Manual Alignment form. Only explicit POST /v1/jobs/{speech_id}/alignment updates the in-memory, revision-guarded cue list. No automatic word/phoneme alignment is introduced. See [Waveform Guide](WAVEFORM_EDITOR_TH.md).

## User-reviewed Manual Timecode Cues (implemented preview)

- POST /v1/jobs/{speech_id}/alignment: requires Content-Type application/json, X-VoxWeaveTTS-Intent: save-manual-alignment. Body {cues:[{segment_index,start_offset,end_offset,start_ms,end_ms}],expected_revision:integer}. Job must be Ready; cues only reference already-filtered Speech display text, use Unicode codepoint offsets and ordered non-overlapping integer milliseconds. At most 128 cues. Returns current Job snapshot and new alignment_revision. Invalid input 400, stale revision/not-ready 409, missing Job 404. No automatic disk storage.
- GET /v1/jobs/{speech_id}: ready Job includes alignment_revision and audio.manual_cues (if submitted), each with derived display_text. Never accept arbitrary text from client Cue.
- GET /v1/playback/state?mode=manual and GET /v1/playback/stream?mode=manual: show only user-reviewed Cue time ranges (blank outside them); subtitle_precision=manual_user_timed or manual_no_cues.
- POST /v1/alignment/evaluate: requires X-VoxWeaveTTS-Intent: evaluate-manual-alignment with JSON candidate/reference Cue arrays. Returns exact span coverage and timing boundary MAE/max/within-100ms, null when not measurable. No waveform or original text is transferred in the evaluation request.

Manual editing is not forced recognition or automatic Thai word alignment. See [Manual Alignment Guide](MANUAL_ALIGNMENT_TH.md).

## Audio Activity Metadata and Caption Mode (experimental)

A successfully generated speech job's `audio` now includes `activity_basis` (PCM16 RMS energy heuristic or `unavailable`) and `word_alignment:false`. Each `audio.segments[]` may include a bounded array `activity_intervals:[{start_ms,end_ms}]` derived from the generated WAV (no waveform bytes or original text are included). If WAV decoding/analysis fails, generation still succeeds without activity intervals.

`GET /v1/playback/state?mode=activity` and `GET /v1/playback/stream?mode=activity` use those intervals to hide captions during silent gaps. `subtitle_precision=pcm16_energy_activity_heuristic` signals that the result is NOT word-level alignment. If absent the mode falls back to the original segment timings and reports `subtitle_precision=generated_segment_fallback_no_activity`. See [Audio Alignment Guide](AUDIO_ALIGNMENT_TH.md).

## Local SSE Playback Stream and Estimated Captions (experimental)

`GET /v1/playback/stream?mode=segment|estimated|activity` is a **read-only Server-Sent Events** stream. Event name: `playback`, numeric `id` is the current in-memory state revision, `data` is the same JSON snapshot as GET /v1/playback/state. A new connection gets the current snapshot immediately, and changed state is pushed without polling. The server limits to 8 concurrent stream viewers per process, sends Keepalive comments, and closes each stream after 20 seconds so the Browser can reconnect. No history is replayed (snapshot-based reconnect). When the stream is unavailable, the OBS overlay polls `GET /v1/playback/state` as fallback.

Both endpoints accept `mode=segment` (default; full generated speech segment) and `mode=estimated` (optional, smaller grapheme-safe caption windows whose timing is **heuristically interpolated** within generated segment durations). Snapshot contains `subtitle_mode`, `subtitle_precision` (generated_segment or estimated_grapheme_windows) and `revision`. Neither mode provides word/phoneme alignment, and neither stream nor REST snapshots are an output-device hardware clock. Invalid mode returns HTTP 400.

See [Local OBS Playback Guide](PLAYBACK_OVERLAY_TH.md).

## Browser Media Playback Clock and OBS Subtitle Relay (implemented)

- GET /v1/playback/state: current local player snapshot (idle, playing, paused, ended, stopped, stale); filtered display_text only, reported current position. clock_basis = browser_html_media_current_time_reported.
- POST /v1/playback/event: application/json and X-VoxWeaveTTS-Intent: report-playback required. Body fields session_id (32 lowercase hex), speech_id (32 lowercase hex), event (start, progress, paused, resumed, seeked, ended, stopped), sequence (increasing integer), position_ms (finite nonnegative number). Start requires a ready Speech Job and valid generated audio timeline; a stale or superseded session returns 409 and missing Job 404.
- GET /overlay or GET /overlay.html: read-only transparent OBS Browser Source polling every 250ms. GET /playback_clock.js: Browser Media Clock Adapter.
- Browser reports currentTime about every 250ms while playing. Captions disappear on stop/end/pause or if no new browser progress is received for over 3 seconds.
- This is SEGMENT-level subtitle timing, not word/syllable/phoneme alignment or hardware-audio frame synchronization. Overlay does not generate or play audio. See [Playback Guide](PLAYBACK_OVERLAY_TH.md).

## Private document reading progress (implemented)

`GET /v1/reading/progress?document_id=<SHA-256>` returns `{schema_version:1, document_id, progress:null|{chunk_chars, chunk_total, next_chunk, updated_at}, revision:<SHA256>}`.

`POST /v1/reading/progress` requires `X-VoxWeaveTTS-Intent: save-reading-progress` and application/json: `{document_id, chunk_chars, chunk_total, next_chunk, expected_revision}`. `POST /v1/reading/progress/clear` requires `X-VoxWeaveTTS-Intent: clear-reading-progress`, application/json and `{document_id, expected_revision}`. On concurrent stale updates returns HTTP 409; invalid data returns 400, missing intent returns 403. Stores only document hash and position counters in `data/reading/positions.json` using atomic replacement; no file content or speech data is persisted. Max 128 tracked documents.

The browser document reader records the next unread chunk only after its WAV media element signals playback ended, and synthesizes no more than one book chunk at a time. `ready` continues to mean **WAV generated**, not played. The reader UI's local playback events are **not** authoritative OBS/subtitle stream timestamps.

## Engine-neutral TXT / Markdown preview (implemented)

POST /v1/documents/preview — JSON with text, format (txt/md), optional title, chunk_chars=100–450 (default 350), page_size=1–30 (default 15), page_index (zero-based). Accepts up to 1,250,000 HTTP request bytes and 300,000 document characters. Returns document_id SHA-256 of canonical text, chapter/chunk counts and metadata, paged chunks with stable offsets in normalized text. Never uses TTS Engine or stores the file on server. Browser supports UTF-8 and Windows-874 file decoding; API itself receives UTF-8 JSON. See [Document Reader](DOCUMENT_READER_TH.md).

## Engine-neutral job queue (implemented)

`POST /v1/jobs` accepts the same text processing, engine, voice, speed, seed and voice_controls fields as `POST /v1/speech`, plus optional `source_message_id` (1–128 chars). Requires `Content-Type: application/json` and header `X-VoxWeaveTTS-Intent: queue-speech`. Returns HTTP 202 with `{schema_version:1, speech_id, state, source, display_text, engine_id, voice_id, audio_ready, ...}`. Duplicates with the same non-empty `source` and `source_message_id` reuse the existing job.

`GET /v1/jobs` returns `jobs[]` snapshots; `GET /v1/jobs/{speech_id}` returns one snapshot; `GET /v1/jobs/{speech_id}/events` returns strictly increasing numbered event records. `GET /v1/jobs/{speech_id}/audio` returns `audio/wav` only in `ready` state, otherwise 409. Unknown ID: 404.

`POST /v1/jobs/{speech_id}/cancel` requires header `X-VoxWeaveTTS-Intent: cancel-speech-job`. Queued jobs are skipped; running jobs are marked cancelled and their results discarded when model inference eventually finishes (the model call is not force-stopped). Without intent: 403.

Limits: 12 in-memory jobs, at most 16 MB WAV per job and 64 MB total WAV memory, 15-minute terminal-job lifetime; 429 when capacity is full and there is no terminal job to evict. All job data disappears on server restart. Status and Event payloads never include private spoken/original text or model error tracebacks.

States: `queued`, `rendering`, `ready`, `failed`, `cancelled`. Events: `speech.queued`, `speech.rendering`, `speech.ready`, `speech.failed`, `speech.cancelled`. **Do not treat ready or generated segment offsets as live playback timestamps.** Audio Playback Clock, OBS Subtitle Event Bus, WebSocket and persistent queue are not yet implemented.

Adapter Protocol Version 1 and capability commercial_status are documented in [Engine-Neutral Core](ENGINE_NEUTRAL_CORE_TH.md).

## Planned; not yet callable

- `WS /v1/speech/stream` streams generated audio
- `GET /v1/voices` and profile management
- `WS /v1/events` reports playback-led speech events
- `GET /v1/playback/snapshot` for overlay reconnect
- `GET /overlay/subtitles` OBS Browser Source

Versioning and authentication requirements will be specified before remote access is implemented.