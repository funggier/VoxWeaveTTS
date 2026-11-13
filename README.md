# VoxWeaveTTS

**Portable Thai-first speech studio** — Windows x64 desktop application with a local Web UI, Thai ONNX speech, source queues, OBS captions and independent workspaces.

> **Windows portable release v0.4.4:** the Windows portable ZIP includes a self-contained Python runtime, dependencies, the MakHam Paradee Thai CPU ONNX model, a Windows launcher executable, Web UI and local data directories. Thai WAV generation was tested from the extracted runtime without a separate Python installation. The FastThaiG2P 325MB model is optional and **not bundled**. Voice cloning, model training, guaranteed commercial rights for added third-party voicepacks, real-time low-latency Discord Gateway support, hardware Playback Clock and automatic word-level subtitle alignment are **not yet implemented**. Discord Desktop RPC message reading was confirmed by a user; official YouTube Live/Discord Bot integrations are not yet verified with authorized live accounts.

## Development preview (not in the published v0.4.4 ZIP)

The source tree now has separate tabs **YouTube LIVE (Browser)** and **YouTube LIVE (API)**. The original API workspace keeps its `live` identifier and saved settings. The experimental Browser workspace starts an isolated Chrome/Edge chat-only window, reads new DOM text messages over local CDP, and routes them into the existing TTS/OBS queue without a YouTube Data API key or Data API quota. It has been tested against a local chat DOM fixture only, **not against authorized real YouTube LIVE chat**. Browser-based automated access is not officially supported and may violate YouTube's terms without prior permission. [Thai browser mode guide](docs/YOUTUBE_BROWSER_READER_TH.md).

**TikTok LIVE (Extension)** replaces the controlled-browser preview. It uses a manually installed Chrome Manifest V3 extension with explicit per-tab activation and local pairing (not CDP). The user has confirmed successful reception of real LIVE comments. Extension v0.2.0 now separates visible comments, author, level, rank, badges and identifiable gift events into structured fields, with opt-in gift reading and source-specific speech connector phrases. The separate **TikTok LIVE (TikFinity)** integration also supports gift events and their reported counts. The new metadata/gift extraction has passed offline tests but is **not yet verified on real LIVE streams**. Automated extraction may be restricted by TikTok terms; check authorization before use. [Thai Extension guide](docs/TIKTOK_EXTENSION_READER_TH.md).

## Model packages (v0.4.2)

VoxWeaveTTS now has a data-only .vwmodel format for optional fixed-voice model packs. One pack specifies its compatible trusted engine adapter, version, multiple selectable voices, SHA-256 checksums, upstream model source, license claim and dependency metadata. The Windows local manager can install multiple packs/versions side by side and remove them independently; no model-supplied Python code runs.

Optional **Vachana Thai (4 voices)** and **FastThaiG2P Kokoro Thai Som (1 voice)** `.vwmodel` archives are available as [separate GitHub Release assets](https://github.com/funggier/VoxWeaveTTS/releases/tag/modelpacks-v0.4.2). Weight files were verified against upstream SHA-256 and each archive embeds original license notices and attribution. The Vachana publisher declares MIT; FastThaiG2P declares Apache-2.0 and its Som TTS training dataset is CC BY 4.0. These are upstream declarations, not an independent audit of all voice/training rights or a commercial-use certification. The v0.4.2 portable ZIP still bundles **MakHam only**; download optional packs separately. [License-by-model catalog (Thai)](model-packs/README_TH.md) · [Package checksums](model-packs/catalog.json).

## Concurrent workspaces and independent voices (v0.4.2)

YouTube LIVE (renamed from the earlier generic Live Reader), TikTok LIVE, Discord Bot and Discord Client are independent source sessions. Switching to Studio, Document Reader or another workspace no longer stops connected readers. Every speech workspace has its own Engine/Model, Voice, Speed and DSP controls with portable per-mode settings. The shared scheduler offers **serial** speech (no overlapping audio, default) or **overlap** (simultaneous playback). New settings apply to the next TTS job; an already rendered WAV is not re-synthesized. The OBS API reports active source subtitles individually, although the default overlay still shows one primary caption.

These concurrent-workspace features are included in the v0.4.2 ZIP. Simultaneous authorized real-account testing across all providers is still pending; offline source and scheduler tests pass. See [Thai mode guide](docs/WORKSPACE_MODES_TH.md).

## Release v0.4.4: YouTube gRPC Live Chat streaming and quota guard

YouTube LIVE now prefers the official `liveChatMessages.streamList` **gRPC** server stream with one connection and continuation tokens. The Windows Portable build must bundle `grpcio` and `protobuf`; ordinary Python installs can enable the optional `youtube-stream` extra. If gRPC is unavailable/unsupported, the adapter uses quota-conscious REST `liveChatMessages.list` polling with at least 30 seconds between calls. Known Google `quotaExceeded` / `dailyLimitExceeded` errors stop automatic retries, `rateLimitExceeded` triggers backoff, and raw error details/credentials are never exposed. The stream itself also costs quota when started. This is included in the published v0.4.4 Windows Portable ZIP. Local gRPC tests pass and the streaming code was user-tested; source-specific quotas, permissions, and real-account behavior remain dependent on Google. [Download v0.4.4 with optional model packs](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.4.4).

## v0.4.3 hotfix: Source reconnect and model package assets

An explicit YouTube LIVE / Discord Bot / Discord Client Connect now reclaims the owner token for that workspace, fixing a stale-token rejection after a backend restart or another browser tab takes control. HTTP 400/401/403/404 errors expose their category without exposing credentials. Provider-side invalid API keys, account access, and quotas still require separate fixes.

[**Release v0.4.3**](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.4.3) offers the Windows Portable ZIP with bundled MakHam alongside **two separately selectable `.vwmodel` assets** (Vachana Thai Four Voices and FastThaiG2P Thai Som) and a SHA-256 checksum file. Both model packs retain upstream license notices, attribution and pinned source hashes. The upstream license declarations do not independently certify every training or voice right.

## New in release v0.4.2

All four live source workspaces (YouTube LIVE, TikTok LIVE, Discord Bot and Discord Client) now have independent, portable **Read sender name before message** preferences, off by default. When enabled, new TTS jobs include the sender before the text; message history remains unchanged. Saved source profiles include the optional Boolean `read_sender_name`, while legacy files are still accepted. See [concurrent workspace guide](docs/WORKSPACE_MODES_TH.md).


The Settings workspace is now dedicated to Model Package management; the top Settings shortcut has been removed. Each speech workspace offers 0.01-step sliders, numerical voice tuning, speed up to x5, seed and independent presets. Folder-based `.json` voice presets live at `presets/` and are re-discovered from the dropdown refresh control; legacy presets remain readable. Automatic reading preferences are no longer silently unchecked on audio errors or Stop; speech pauses with a retry action instead. Only MakHam Paradee weights are bundled into Windows Portable; optional Vachana and FastThaiG2P `.vwmodel` files are published separately under their upstream declared licenses, with full notices and an explicit unverified-training-rights warning.

## Goals

- Thai pronunciation overrides (e.g. `อมตะ`), with original subtitle spelling retained.
- User-defined spoken-word replacement, subtitle masking, skipped words, and inserted silence.
- Selectable voice profiles, expressive controls, model adapters and A/B audition.
- Live Discord / YouTube chat input with queueing and content filtering.
- Playback-clock-driven subtitle events for OBS Browser Source and external apps.
- Windows portable ZIP: all settings, voice references and model caches under a movable root, without forced writes to the system drive.

## Install and run — Windows 10/11 x64 portable

1. Download `VoxWeaveTTS-v0.4.4-portable.zip` from GitHub Releases.
2. Extract the **entire** ZIP to a writable folder, for example `T:\\Apps\\VoxWeaveTTS`. Do not run the EXE directly from inside the ZIP.
3. Double-click `VoxWeaveTTS.exe`. It starts the local server and opens your default browser (Firefox or Chrome) at `http://127.0.0.1:8765/`.
4. Select the available **MakHam Paradee** engine, enter Thai text and generate speech. Other modes include document reader, Discord Client, official chat inputs, pronunciation rules, source profile import/export and OBS subtitles.
5. Close the desktop launcher window using **Stop & Exit** to terminate its private server. Keep it open while using the app.

No separate Python, Node, GitHub CLI, service, admin install or cloud login is required for local speech. Windows .NET Framework 4.x is used by the tiny desktop launcher; if the EXE is blocked, try `Start-Console.cmd`. Models/user settings/caches stay within the extracted folder. For troubleshooting and legal notices, see [Windows Portable Guide](docs/PORTABLE.md).

## Development setup (source checkout)

1. Install `uv` and GitHub CLI (`gh`) for development setup. Run `powershell -ExecutionPolicy Bypass -File scripts/Install-ThaiEngine.ps1` in the project directory. The optional CPU engine and ~326 MB voice model are stored under the project root.
2. Run `Start-Dev.cmd` (picks the local `.venv` Python first).
3. Open <http://127.0.0.1:8765/> and click **สร้างเสียง WAV** to synthesize and audition Thai speech; no voice cloning in this engine. Select one of two locally installed Thai Engines, use paired Slider/Numeric controls for Speed, Gain, Pitch, Bass and Treble, edit pronunciation/replacement rules directly, and save/load Voice Presets. **Seed** remains an advanced reproducibility option, not voice timbre. FFmpeg with Rubber Band is an optional developer dependency for Pitch/EQ; volume and speed work independently. A fresh ONNX session still reproduces audio for fixed text/speed/seed on the tested runtime.
4. Use `scripts/Generate-ThaiSample.ps1` while the local server is running to save `output/api_demo.wav`.
5. Run `Test-Dev.cmd` for unit tests.

The Python `.venv` remains a developer environment; end users should use the portable ZIP and its bundled interpreter/model. Optional developer engines require separate license checks.

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

## TikTok LIVE comments — local TikFinity Desktop bridge (v0.4.1)

TikTok does not document a general public LIVE chat API. The new independent **TikTok LIVE** workspace reads chat comments via TikFinity Desktop's local Event WebSocket (`ws://localhost:21213/`) from the same PC and reuses the global Thai TTS Engine, sequential speech queue, per-source filters, completed-message history, OBS captions and separate JSON settings profiles. TikFinity Desktop must be installed and connected to your own live stream; no TikTok username/password/cookie is handled by VoxWeaveTTS. Non-chat events such as gifts and likes are deliberately ignored. The connection uses TikFinity's local API but is not an official TikTok integration, and was tested offline only; see [Thai setup and known limitations](docs/TIKTOK_LIVE_TH.md).

## Official YouTube Live / Discord message inputs (opt-in preview)

Live and Discord workspaces now include read-only official message source adapters using user-provided YouTube Data API Key/liveChatId or Discord Bot Token/Channel ID. Messages are deduplicated and moderated before entering a bounded in-memory queue (40 backend pending, 12 browser waiting items). The three source modes share a serial TTS queue implementation; browser-completed history is configurable from 0 to 100 (20 default) and only finished messages are removed. Each live mode can export/import an independent settings JSON including its sensitive credentials and blank fields; Export opens a Save As location/file-name picker in Chrome (File System Access) and Firefox (native Windows dialog via the local server). Import fills the form without auto-connecting. **These JSON profiles store API Keys, Bot Tokens and Client Secrets in plaintext. Keep them private and out of Git.** The first page is only a baseline, not automatically spoken; the user can manually select messages or use sequential TTS auto-reading (ON by default after the user explicitly connects the source; can be unchecked). Only the active workspace can read messages and publish to the one OBS Overlay. Credentials are never committed or persisted by the app.

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