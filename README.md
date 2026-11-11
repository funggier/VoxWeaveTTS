# VoxWeaveTTS

**Portable Thai-first voice studio and real-time speech platform** — work in progress, currently at M1 CPU audio preview.

> **Current status (v0.3.0.dev18 shared live queue and settings-profile preview):** local text processing and **real Thai WAV generation with two CPU ONNX Engines**, FastThaiG2P and MakHam Paradee, when the optional model/runtime are installed. **Voice cloning/fine-tuning, native expressive controls, live-account-verified YouTube Live/Discord Bot adapters (Discord Desktop RPC was user-confirmed), word/phoneme subtitle alignment, a native hardware Playback Clock, and a bundled Windows portable executable are NOT implemented.** The user confirmed working Discord Desktop RPC message reception on dev17; YouTube Live and Discord Bot adapters have not been verified using authorized live credentials. The preview now offers native Speed plus optional post-DSP Pitch, Gain, Bass and Treble.

## Goals

- Thai pronunciation overrides (e.g. `อมตะ`), with original subtitle spelling retained.
- User-defined spoken-word replacement, subtitle masking, skipped words, and inserted silence.
- Selectable voice profiles, expressive controls, model adapters and A/B audition.
- Live Discord / YouTube chat input with queueing and content filtering.
- Playback-clock-driven subtitle events for OBS Browser Source and external apps.
- Windows portable ZIP: all settings, voice references and model caches under a movable root, without forced writes to the system drive.

## Run the Thai audio preview (Windows)

1. Install `uv` and GitHub CLI (`gh`) for development setup. Run `powershell -ExecutionPolicy Bypass -File scripts/Install-ThaiEngine.ps1` in the project directory. The optional CPU engine and ~326 MB voice model are stored under the project root.
2. Run `Start-Dev.cmd` (picks the local `.venv` Python first).
3. Open <http://127.0.0.1:8765/> and click **สร้างเสียง WAV** to synthesize and audition Thai speech; no voice cloning in this engine. Select one of two locally installed Thai Engines, use paired Slider/Numeric controls for Speed, Gain, Pitch, Bass and Treble, edit pronunciation/replacement rules directly, and save/load Voice Presets. **Seed** remains an advanced reproducibility option, not voice timbre. FFmpeg with Rubber Band is an optional developer dependency for Pitch/EQ; volume and speed work independently. A fresh ONNX session still reproduces audio for fixed text/speed/seed on the tested runtime.
4. Use `scripts/Generate-ThaiSample.ps1` while the local server is running to save `output/api_demo.wav`.
5. Run `Test-Dev.cmd` for unit tests.

The Python `.venv` is a developer environment, **not the final portable executable**. Offline synthesis works once the engine and model are installed.

## Engine-neutral foundation (implemented preview)

The text pipeline, engine registry, queue, event statuses and result delivery are separate from model implementations. The core runs on **Python standard library only**; actual inference still requires the selected engine's optional dependencies and model files. An independently trained Thai voice engine can be registered through the **Adapter API v1** without changing the HTTP server, processing rules or job queue.

- Job states: `queued → rendering → ready`, or `cancelled/failed` (ready means generated, not played).
- FIFO + source message dedup + explicit cancellation + bounded in-memory audio / job limits.
- Versioned preparation events; browser media-clock reports now drive a local OBS segment-level subtitle overlay (not sample-accurate OBS sync).
- All engines retain `commercial_status: review_required` unless their complete artifact and dependencies pass an audit.

See [Engine-Neutral Core architecture (Thai)](docs/ENGINE_NEUTRAL_CORE_TH.md).

## Readable Rules / Pronunciations JSON editor

The existing **Rules JSON array** and **Pronunciations JSON object** now provide format, syntax/type check, download and quick-entry actions. Quick entry uses JSON.stringify to escape quotation marks, backslashes and Unicode safely. Formatting preserves the rule array's order. **Save in Program** now persists validated config under ignored local `data/filters/rules.json` and `data/dictionaries/pronunciations.json`; saved rules reload on app start and are shared by all Engines. The editor also supports importing previously exported JSON files. Concurrency is protected by section-specific SHA-256 revisions (HTTP 409 on conflict), and file downloads remain separate from server persistence. See [Thai JSON pronunciation guide](docs/PRONUNCIATION_JSON_TH.md).

## Browser media-clock subtitle overlay (implemented preview)

When a generated WAV actually plays in the document reader or job queue player, a shared browser media-clock adapter reports currentTime, seek, pause, resume, end and stop to the local Playback API. A read-only transparent OBS overlay can open http://127.0.0.1:8765/overlay. The overlay follows Browser-reported time, hides silenced segments, and automatically hides stale captions. It does NOT play audio itself; capture audio from the original player separately in OBS. This is SEGMENT-level timing, not word/phoneme alignment or hardware-output-accurate synchronization. See [Playback and OBS guide (Thai)](docs/PLAYBACK_OVERLAY_TH.md).

## Discord Desktop Client Reader — select a single channel

A dedicated Discord Client workspace can subscribe to new MESSAGE_CREATE events for one explicitly selected text-channel ID via the official Discord Desktop Local RPC. It uses an authorized Discord developer application, explicit user approval and rpc + messages.read scopes; no user-token self-bot or scraping. Channel IDs are checked for every incoming event and switching channels/modes stops the previous feed. Global Engine/Voice/Rules and the shared OBS Overlay remain unchanged.

Discord restricts RPC access to approved apps or testers. The room selector and RPC protocol have offline tests, now use documented RPC AUTHORIZE arguments (client_id and scopes only), preserve the registered redirect URI for the token exchange, and expose safe OAuth error identifiers and failure-stage diagnostics; a live user-account connection has not yet been verified with approved real credentials. Switching rooms stops the old feed and speech queue but preserves the user-selected auto-read checkbox; if the RPC pipe closes or authorization fails, enter your app secret again and reconnect explicitly rather than relying on a stale session. The OAuth token HTTP request now sends an identifiable application User-Agent; without it, the default Python urllib User-Agent was observed to receive HTTP 403 on this machine. A local fake-credential request now reaches OAuth validation and receives HTTP 400 invalid_client; this is not proof of a successful authorized account connection. A separately opened OAuth2 URL Generator does not subscribe the desktop RPC session. Match the registered redirect URI with the exact URI displayed in Discord (for example `http://127.0.0.1:8765` versus `/callback`). [Discord Client Reader Guide (Thai)](docs/DISCORD_CLIENT_READER_TH.md).

## Official YouTube Live / Discord message inputs (opt-in preview)

Live and Discord workspaces now include read-only official message source adapters using user-provided YouTube Data API Key/liveChatId or Discord Bot Token/Channel ID. Messages are deduplicated and moderated before entering a bounded in-memory queue (40 backend pending, 12 browser waiting items). The three source modes share a serial TTS queue implementation; browser-completed history is configurable from 0 to 100 (20 default) and only finished messages are removed. Each live mode can export/import an independent settings JSON including its sensitive credentials and blank fields; import fills the form without auto-connecting. **These JSON profiles store API Keys, Bot Tokens and Client Secrets in plaintext. Keep them private and out of Git.** The first page is only a baseline, not automatically spoken; the user can manually select messages or use sequential TTS auto-reading (ON by default after the user explicitly connects the source; can be unchecked). Only the active workspace can read messages and publish to the one OBS Overlay. Credentials are never committed or persisted by the app.

The adapters are tested against mocked Official API responses but **not yet verified with a user's live authorized YouTube/Discord account**. YouTube uses list-polling with provider intervals, Discord uses REST polling with rate-limit backoff; neither is a low-latency gateway. See [Live Input Adapters Guide (Thai)](docs/LIVE_INPUT_ADAPTERS_TH.md).

## Independent workspaces and global Engine/Voice settings (preview)

The UI now separates Studio, Document Reader, Live text simulation, Discord text simulation, Speech Queue/Subtitle/Manual Alignment, shared Pronunciation Rules, and shared Engine/Voice settings. Each mode keeps its own editable text/player; all modes share the global model, voice, speed, DSP, Seed, presets and dictionary/rules. The global voice defaults can be saved atomically to a gitignored local JSON file and reloaded next session.

Switching modes synchronously stops other audio/reader autoplay, revokes the previous playback ownership token and clears the **single OBS Overlay**; a bounded SSE channel, BroadcastChannel and polling notify other tabs. Studio WAVs now use the job/clock API so they also support OBS captions. **Live/Discord retain local simulation and can optionally connect to Official APIs** using the user's own credentials; live account testing is still pending. See [Workspace modes guide (Thai)](docs/WORKSPACE_MODES_TH.md).

## Safer Thai caption boundaries (fixed in v0.3.0.dev9)

Estimated captions now break only at explicit whitespace or punctuation. Arbitrary grapheme-count cuts could previously strand Thai preposed vowels or final consonants across caption windows. If a continuous Thai text run has no reliable separator, the whole generated speech segment remains one caption rather than inventing Thai word boundaries. The OBS overlay also no longer forces arbitrary CSS word wrapping.

The engine-neutral Document Reader prefers punctuation/whitespace and marks any hard-limit Thai fallback in the returned chunk metadata and the UI. Chunker revision is part of the document ID hash to avoid resuming old ordinal bookmarks at the wrong text after changed boundaries; reopen your document, select the correct chunk and save the bookmark again. This is **not** a Thai dictionary tokenizer or word-level forced aligner. See [Document Reader](docs/DOCUMENT_READER_TH.md).

## Browser Waveform Editor (implemented preview)

The Manual Alignment panel can now display the **actual WAV PCM16 peak envelope** with high-DPI canvas, Speech/Silence regions and manual Cue spans. Zoom 1–32×, pan, click to seek, drag to mark Start/End, or nudge the audio cursor by arrow keys (25ms or Shift+arrow 5ms). The Browser loads only already-rendered local WAV from the Speech Job and never uploads audio to external services. Waveform analysis is sample-energy visualization, **not** automatic speech/word alignment. PCM16 mono/stereo WAV is supported; if unsupported, the numeric editor still works. See [Waveform Editor (Thai)](docs/WAVEFORM_EDITOR_TH.md).

## User-reviewed manual word/phrase subtitle timecodes (experimental)

A model-independent Manual Alignment editor in the Speech Queue lets the user select a span of filtered display text, mark WAV playback start/end positions and apply explicit subtitle cues to a ready Job. Open /overlay?mode=manual to display only those user-marked text spans; unannotated regions remain blank. Timecodes are memory-only and exportable/importable as JSON; another tab cannot silently overwrite revisions. A reference timing evaluation API provides exact-span MAE and coverage metrics. This is **not automatic forced alignment**. See [Manual Alignment Guide (Thai)](docs/MANUAL_ALIGNMENT_TH.md).

## Audio-signal subtitle activity mode (experimental)

The shared Speech Coordinator now runs a lightweight **stdlib-only PCM16 audio energy analyzer** after every WAV render, extracting speech-like activity and silent gaps within generated speech segments. It uses a pluggable AudioAlignmentProvider contract and publishes only bounded interval metadata. Use `http://127.0.0.1:8765/overlay?mode=activity` to hide captions in detected silent gaps. This is **audio activity detection, not word/syllable forced alignment or ASR**; unrecognized WAV formats fall back explicitly to generated-segment timing. No third-party model or training data was added. See [Audio Alignment Guide (Thai)](docs/AUDIO_ALIGNMENT_TH.md).

## Low-latency subtitle stream and estimated caption windows (experimental)

The local read-only OBS Overlay now uses **Server-Sent Events** (`GET /v1/playback/stream`) to receive changed playback snapshots; it falls back to `GET /v1/playback/state` when the stream disconnects. An opt-in URL, `http://127.0.0.1:8765/overlay?mode=estimated`, shows shorter Unicode-safe text windows within each WAV speech segment. Their timing is **estimated from grapheme counts**, not a forced aligner or true word/phoneme timing, and may not follow Thai speech precisely. Default `/overlay` retains the real generated-segment boundaries. See [Playback and OBS guide](docs/PLAYBACK_OVERLAY_TH.md).

## Resume reading and one-chunk-at-a-time playback (implemented preview)

TXT/Markdown documents now have **local private reading bookmarks** stored under `data/reading/positions.json`, keyed by normalized document SHA-256, without storing file content, filenames or paths. Reopen the original file to retrieve a matching bookmark; changed chunk size invalidates that index. You can manually save/clear position, play/pause/stop one chunk, and opt in to advancing to the next chunk after the browser media element emits its `ended` event. Playback advances a bookmark **only on completed audio**, never when a WAV is merely generated. A single outstanding synthesis per document reader prevents full-book preload. Browser autoplay policies may require manual Play. **This is not an OBS-synchronized audio playback clock or live subtitle event stream.**

See [Document Reader guide (Thai)](docs/DOCUMENT_READER_TH.md).

## Text/Novel import (implemented preview)

The web UI can open a **local UTF-8 or Thai Windows-874 .txt/.md file**, normalize Markdown narration, identify chapters and page through short chunks **without loading any speech model**. A chosen chunk can be copied into the existing text editor or sent to the engine-neutral speech queue with the current voice/rule settings. This is manual chunk preparation, **not full-book autoplay or persistent reading position**. Documents are retained only in the browser page session, not stored by the server.

See [Engine-neutral Document Reader (Thai)](docs/DOCUMENT_READER_TH.md).

## API

- `GET /v1/status` — build status and explicit capability flags.
- `GET /v1/rules` — locally stored replacement rules, if configured.
- `GET /v1/pronunciations` — locally stored pronunciation overrides, if configured.
- `POST /v1/documents/preview` — TXT/Markdown normalization, chapter detection, deterministic chunk pagination and metadata (no model required).
- `POST /v1/text/process` — deterministic filter, replacement, silence and pronunciation processing; optional `match_mode: five_run` safely maps repeated chat 5s to speech while retaining the original subtitle.
- `GET /v1/engines` and `GET /v1/voices` — two Thai CPU engine adapters, their readiness, voice IDs and detailed DSP control schema.
- `POST /v1/jobs`, `GET /v1/jobs` and `GET /v1/jobs/{id}` — engine-neutral asynchronous audio preparation queue; `GET /v1/jobs/{id}/events`, `GET /v1/jobs/{id}/audio` and `POST /v1/jobs/{id}/cancel`.
- `POST /v1/speech` — generate Thai PCM16/WAV through the optional FastThaiG2P CPU backend (500 spoken characters max per request), with optional reproducible `seed`.
- `GET/POST /v1/settings/synthesis` — view/store a preferred seed in local portable settings (POST requires an explicit intent header).
- `GET/POST /v1/presets` — list/save local private Voice Studio Presets (POST requires explicit intent header).
- `GET /` — local text and WAV preview.

Example (PowerShell):

```powershell
$body = @{
  text = "ชายหนุ่มพบคำต้องห้ามและบรรลุขั้นอมตะ"
  rules = @(@{ match="คำต้องห้าม"; mode="silence"; display="***"; silence_ms=400 })
  pronunciations = @{ "อมตะ" = "อะ มะ ตะ" }
} | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:8765/v1/text/process -Method Post -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

The response includes separate **display_text** and **speech segments**. Silence segments are explicit timeline instructions; a future audio playback coordinator will synthesize the actual silence.

## Repository and privacy

The MIT license applies to **our code only**. Models, voice samples, dictionaries, proprietary services, and third-party dependencies keep their own terms. Never commit reference recordings, tokens, credentials, generated audio, downloaded model weights or local settings. The repository explicitly excludes those directories.

## Documentation

- [ภาษาไทย / รายละเอียดโปรเจกต์](README_TH.md)
- [Project background and design rationale (Thai)](docs/PROJECT_VISION_TH.md)
- [Detailed development plan and acceptance criteria (Thai)](docs/DEVELOPMENT_PLAN_TH.md)
- [Requirement traceability (Thai)](docs/REQUIREMENTS_TH.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API Contract](docs/API.md)
- [Portable distribution plan](docs/PORTABLE.md)
- [Roadmap](docs/ROADMAP.md)
- [Licensing and privacy](docs/SECURITY.md)
- [M1 real Thai audio setup and verification (Thai)](docs/M1_AUDIO_TH.md)
- [Voice Studio engines and control ranges (Thai)](docs/VOICE_STUDIO_TH.md)
- [Voice cloning and fine-tuning plan (Thai)](docs/VOICE_TRAINING_TH.md)
- [Commercial-first license policy and model audit (Thai)](docs/COMMERCIAL_LICENSE_POLICY_TH.md)
- [Engine-neutral Core, Registry and Queue (Thai)](docs/ENGINE_NEUTRAL_CORE_TH.md)
- [TXT/Markdown Document Reader (Thai)](docs/DOCUMENT_READER_TH.md)