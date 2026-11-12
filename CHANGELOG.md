# Changelog

The v0.4.0 release is the first distributable Windows portable bundle. Older dev snapshots below were development-only.

## 0.4.2.dev1 — Concurrent workspaces, per-mode voices and selectable audio policy (development, 2026-11-12)

- Rename generic Live Reader navigation/title to **YouTube LIVE**, retaining the existing live-mode ID and saved connection profiles.
- Replace single-active workspace ownership with per-mode ephemeral authorization and independent YouTube/Discord source sessions; browser TikFinity continues when users change tabs.
- Add Engine/Model, Voice, Speed and DSP controls in every speech workspace. Updates apply to the next TTS job, never rewrite an already rendered WAV. Preferences persist in data/settings/mode-voices.json.
- Add a global audio policy: **serial FIFO** (no overlapping audio, default) or **overlap** (allow simultaneous playback of different workspaces). Already-playing audio is not stopped when the policy changes.
- Support concurrent browser audio clocks and mode-specific subtitle snapshots; existing OBS overlay continues to show one primary caption.
- Expand Python and JS regression tests for multi-source connections, safe per-mode tokens, independent voice controls, persistent settings and both audio queue policies.
- Development preview only: Windows Portable Release v0.4.1 remains unchanged; simultaneous provider accounts have not been live-verified.

## 0.4.2.dev0 — Data-only model packages and multiple Thai voices (in development, 2026-11-12)

- Introduced a versioned .vwmodel ZIP format with strict JSON Manifest: supported Engine Adapter, package ID/version, voices, per-file size/SHA-256, source revision, SPDX license claim/attribution/review status and declared runtime dependencies.
- Added an atomic, local-only installer, separate installed-package folders per model/version, safe removal and Windows native picker triggered from the Web UI in both Firefox and Chrome. Packages cannot inject Python, DLL, EXE or scripts; ZIP traversal/symlink/unlisted files and hash mismatches fail closed.
- Model Package Manager displays available packages, voices, licenses, review state, dependencies and removal controls. Installing/removing through the local UI refreshes Engine Registry; CLI supports list/install/remove and building a Vachana development pack.
- Added multi-voice support to EngineInfo, Voice Studio selection, global-voice settings and presets. Existing single-voice engines remain compatible; one package becomes one separately selectable Engine with its own voice choices.
- Added a trusted Vachana Thai VITS ONNX adapter for four fixed voices (two female, two male) using local weights only (no auto-download or package code execution).
- Created and installed Vachana Four Voices v1.0.0 .vwmodel locally. Generated real Thai WAV from all four voices using the installed package path; the locally generated file is excluded from Git and public release pending rights review.
- Package support is **not present in the existing v0.4.1 release**. The developer venv has Vachana dependencies; the v0.4.1 portable runtime is not guaranteed to contain them. License review_status stays review_required; an unverified SPDX declaration is not redistribution clearance.
- Added model package integrity, multi-version isolation, HTTP origin/intent security and UI smoke regression tests. No third-party weight files are committed to the repository.

## 0.4.1 — TikTok LIVE via local TikFinity Event API (2026-11-12)

- Added an independent TikTok LIVE workspace to Windows Portable, with the same global Thai TTS Engine, serial speech queue, OBS subtitle ownership, per-message read states and capped read-message history as Discord and YouTube.
- Connects to the TikFinity Desktop Local Event API (`ws://localhost:21213/`) through a browser WebSocket. Reads **chat comments only**; excludes gifts/likes/follows to prevent unintended speech and queue overload. No TikTok credentials, cookies, unofficial scraping libraries or packaged TikFinity software.
- Restricts WebSocket targets to the documented local port on localhost/127.0.0.1; handles malformed events, duplicate message IDs, URLs, command messages, keyword filters, disconnects and source switches.
- Added browser-compatible Export/Import settings profiles for TikTok without a credential field; Import never connects automatically.
- Added offline fake TikFinity WebSocket tests, full shared TTS queue tests, Python workspace/markup tests, Firefox native Save As validation, and Thai installation/limitations documentation.
- The local TikFinity endpoint was **not available on the test machine**, so actual TikTok LIVE comments remain unverified. A live stream and TikFinity Desktop are required for user-side verification.

## 0.4.0 — First Windows portable application release (2026-11-12)

- Built a Windows 10/11 x64 portable ZIP with a self-contained Python 3.11 interpreter, standard library, ONNX inference dependencies, Web UI, Thai speech source, Windows `VoxWeaveTTS.exe` GUI launcher and diagnostic `Start-Console.cmd`. No end-user Python, Node, GitHub CLI or installation required.
- The app launcher manages one loopback-only local server on port 8765, opens the system default browser (Firefox/Chrome supported) and stops the child server when its window closes. Does not alter Windows PATH, registry or services.
- Included MakHam Paradee CPU INT8 model and its separately published Apache-2.0 license provenance/attributions for usable Thai WAV synthesis out of the box. The 325MB FastThaiG2P checkpoint, personal voice recordings, user data, caches, saved tokens and unpublished model packs are intentionally excluded.
- Kept app-generated settings/models/caches/outputs under the movable extracted folder. Documented clean extraction, fallback console launcher, manual Discord RPC approval, model licensing, supported workflows and known limitations.
- Added an automated portable runtime smoke test that validates the packaged Python interpreter and generates real Thai WAV from the bundled MakHam ONNX model. The downloadable ZIP has SHA-256 verification.
- Known limitations: no voice cloning, model training, native GPU inference or independently audited third-party user-supplied voicepacks; YouTube Live / Discord Bot connections remain unverified with authorized real accounts. Use the included notice/license files before commercial redistribution.

## 0.3.0.dev19 — Select Export file location in Firefox and Chrome (2026-11-12)

- Replace automatic browser download on source profile Export with an explicit **Save As** location/file-name picker, preserving all fields, blank values and plaintext user-supplied credentials in the JSON profile.
- Chrome uses the native browser File System Access `showSaveFilePicker` API, invoked synchronously from the Export button's user gesture. It writes UTF-8 JSON directly to the user-approved destination, never silently downloading into Downloads.
- Firefox does not expose `showSaveFilePicker`: the local VoxWeaveTTS Windows backend opens a native Tk Save As dialog. The Firefox browser POST uses explicit custom intent, same-origin Origin/Sec-Fetch-Site and loopback Host checks; no arbitrary target pathname, token or file contents are returned by the server. Only a confirmed user-selected .json path is written, atomically.
- Canceling either dialog saves nothing; native Save As unavailability returns a clear failure rather than silently writing credentials to the downloads folder. Save/Import does not connect any source.
- Added offline Chrome/Firefox mock tests, native selected-path write tests, HTTP origin/intent rejection and no-secret-leak tests. Verified Tk can initialize in the user's Windows Python environment. The system chooser UI is user-operated and was not autonomously clicked during tests.

## 0.3.0.dev18 — Shared live FIFO, capped read history, source-settings export/import (2026-11-12)

- Unified YouTube Live, Discord Bot, and Discord Desktop RPC auto-reading into the same per-mode serial speech queue. Each message progresses through queued → preparing WAV → reading → read on the browser audio ended event; stop, mode changes and feed failures cancel pending work.
- Preserve older unread items when overloaded: browser auto-read retains up to 12 waiting messages plus the active item and rejects additional arrivals with a skipped counter; backend queue preserves up to 40 pending items and rejects new overflow instead of evicting older unread items.
- Show per-message states and queue counts, and offer a per-mode adjustable **completed-message history** limit (default 20, allowed 0–100). Only completed messages are pruned FIFO; queued/preparing/playing messages are retained. Manual and skipped browser history is separately bounded to 25.
- Added per-provider **Export/Import JSON settings** buttons for all three live source modes. Profiles round-trip every editable source field, including plain-text API Keys, Bot Tokens, Discord Application Client Secrets, incomplete fields and empty values. The files are created/read **in the browser** without uploading them or starting connections; only the selected source mode can load a profile.
- Import validates schema/version, size and mode *before* modifying inputs; if a connection is active it is stopped first. Secret-bearing files are explicitly marked unencrypted on the UI; malformed JSON or errors never echo raw user data into status. Connection-time validation remains separate from draft profile validity.
- Added offline end-to-end smoke tests for high-volume FIFO flow, read-only history pruning, pause/resume/stop, and full/blank/invalid secret-bearing profile export/import for all three modes. Included both suites in GitHub Actions.
- User previously confirmed actual Discord Desktop RPC message receipt on dev17. The dev18 queue/profile tests use fake messages and credentials; an authorized external account retest was not performed as part of these automated tests.

## 0.3.0.dev17 — Fix Discord OAuth HTTP 403 from default Python User-Agent (2026-11-12)

- Identified an HTTP-level request issue in the Discord OAuth token exchange: on the user's Windows host, harmless test requests using Python's default `Python-urllib/3.11` User-Agent received HTTP 403; the same OAuth endpoint with an explicit, application-identifying User-Agent returned the expected HTTP 400 `invalid_client` for intentionally fake credentials.
- Added a versioned `VoxWeaveTTS (https://github.com/funggier/VoxWeaveTTS, <version>)` User-Agent to OAuth requests, and used Discord's explicitly versioned `/api/v10/oauth2/token` route. Form encoding and no-redirect handling remain intact.
- Clarified the generic OAuth 403 error to distinguish request blocking from an OAuth code/redirect mismatch. Never include secrets, authorization codes or provider response bodies in error output.
- Added regression tests for User-Agent, endpoint version, and safe HTTP 403 reporting. Verified the real `oauth_exchange()` function with **fake-only** credentials now receives expected `invalid_client (HTTP 400)` from Discord instead of HTTP 403.
- This demonstrates that the token endpoint can be reached by the fixed HTTP client. A real authorized Discord account/token exchange and message subscription are still unverified; reconnect and explicitly approve the app to test them.

## 0.3.0.dev16 — Diagnose Discord RPC OAuth error 5000 (2026-11-12)

- Corrected the Local RPC AUTHORIZE payload to match Discord's documented argument schema: client_id and scopes only. The redirect_uri added to AUTHORIZE in dev15 is **not listed** in the official RPC arguments; redirect_uri remains part of the token exchange.
- For RPC error code 5000, inspect only an allowlisted OAuth error identifier from Discord's bounded "OAuth2 Error: <code>:" message, such as invalid_scope, invalid_request or unauthorized_client. Never expose arbitrary provider text, account data, auth codes, Client Secret, or Access Tokens.
- Confirmed that an RPC 5000 error occurs during AUTHORIZE, **before** receiving an authorization code; the error itself does not identify the root cause. The next safe diagnostic is whether it is invalid_scope (possibly missing approved RPC access/tester status).
- Added fake-transport regression tests for 5000 allowlist and undocumented-argument removal; retained all existing protections and auto-read defaults.
- A real Discord Desktop session with the user's authorization was not attempted by the regression suite; successful live message receipt is not claimed.

## 0.3.0.dev15 — Discord RPC OAuth code-exchange diagnostics (2026-11-12)

- Added the configured registered `redirect_uri` to the Discord Desktop RPC `AUTHORIZE` command as well as the OAuth token exchange. Previously only the token request carried it, potentially producing an authorization code associated with a different URI. The public Discord RPC documentation lists the short-form AUTHORIZE arguments; this fix is regression-tested with a fake transport, but real token-exchange behavior still requires a fresh user-approved session.
- Replaced the single generic OAuth denial message with privacy-preserving, allowlisted OAuth response error identifiers (`invalid_client`, `invalid_grant`, `unauthorized_client`, `invalid_request`, etc.) and HTTP status. Provider error descriptions, auth codes, secrets, tokens and raw responses remain hidden.
- Added `failed_phase` to the Discord Client status only after terminal failure; the UI identifies whether failure happened at consent, token exchange or a later stage without exposing credentials.
- Added tests for matching authorization and exchange URIs, safe OAuth HTTP error handling and preserving the failed RPC phase. No real user credentials were saved or included in tests.
- The user's observed `Discord RPC OAuth denied` means token exchange failed, not channel polling. The exact provider error remains unknown until the user reconnects after updating; do not assume a successful account connection.

## 0.3.0.dev14 — Default-on live reading and RPC connection diagnostics (2026-11-12)

- Enabled the automatic-read checkbox by default for YouTube Live, Discord Bot, and Discord Client. External sources still require explicit Connect, and users may disable the checkbox at any time. Mode/room changes stop the previous source and clear speech queues while preserving the user's checkbox preference.
- Added safe Discord RPC connection-stage diagnostics: named pipe, handshake, waiting for permission, OAuth code exchange, authentication and channel subscription. An accepted source-start HTTP request is no longer described as a completed connection.
- Tolerate idle reads while the Discord permission dialog remains open, with a bounded 90-second consent period. Incomplete RPC frames remain fatal to prevent desynchronization.
- Expose only allowlisted RPC error hints and connection-phase names, not user data, tokens, or raw provider messages.
- Clarified that an OAuth2 URL Generator flow does not connect a Discord Desktop RPC session. Use the app's Connect control; the registered redirect URI must match the URI shown in the actual authorization dialog, including any path.
- Local Python and Node regression tests cover the changes. Live, authorized Discord channel subscription is not yet verified.

## 0.3.0.dev13 — Discord Client RPC disconnect safety (2026-11-11)

- Distinguished idle RPC reads from partial-frame timeouts; partial frames are now terminal rather than silently returning with a corrupted frame boundary.
- Handshake/authentication failures and an established RPC session being disconnected, closed, or failing a PONG now require an explicit fresh connection and user consent. Invalid sessions are discarded without cancelling the source worker before it can publish an actionable error state.
- Discord Client auto-read is reset when selecting a different room, and terminal source errors clear pending browser auto-read messages. Other source modes retain their existing behavior.
- Expanded fake-transport and browser regression checks for idle timeouts, RPC close/disconnect, initial handshake failure, SourceManager fatal status, and room-switch consent.
- Official Discord Desktop with an authorized application/tester is **not** available in this test environment; no live-account compatibility is claimed.

## 0.3.0.dev12 — Discord Desktop Client Reader with selectable room (2026-11-11)

- Added a dedicated Discord Client Reader workspace for a user's own Discord Desktop account, separate from the Discord Bot Reader.
- Supports explicit text-channel selection by Discord Channel ID. Official Local RPC subscribes to MESSAGE_CREATE only for the selected channel, validates every event's channel_id again, and filters unrelated rooms, edits, bots, webhooks and blocked messages.
- Implemented consent-based Discord IPC HANDSHAKE, AUTHORIZE with rpc + messages.read, OAuth code exchange on the official Discord endpoint, AUTHENTICATE and bounded SUBSCRIBE. No user tokens, self-bots, browser cookie inspection, internal APIs, screen scraping or packet interception.
- Reader uses centralized Engine/Voice/DSP/Rules and the single active playback/OBS overlay; changing mode stops source and audio. Credentials are temporary, and automatic reading is opt-in.
- Added mock IPC protocol and room-selection tests. Actual user-account connection remains unverified until Discord RPC application/tester permissions and explicit consent are available.

## 0.3.0.dev11 — Official YouTube Live/Discord read-only message adapters (2026-11-11)

- Added opt-in read-only Official API source adapters for YouTube Live Chat (liveChatMessages.list with liveChatId or video ID, nextPageToken, pollingIntervalMillis) and Discord Bot REST channel message polling (after Snowflake ID, rate-limit Retry-After). Initial API history is deliberately skipped.
- Added bounded per-server SourceManager workers, owner-mode checks and credential-in-memory handling, source-message deduplication, text moderation, constrained 40-message backend queue and safe rate-limit/backoff logic. Source workers are stopped on mode activation; no user tokens/self-bots, scraped pages, cross-host requests or disk credential persistence.
- Added POST /v1/sources/start, /stop, /drain and GET /v1/sources/status?mode=live|discord, with explicit intent headers and current mode ownership verification.
- Added Live/Discord UI controls to connect and disconnect Official API, view and select messages, enter local filter lists, and opt in to sequential automatic TTS reading. Auto-read is OFF by default; existing manual simulation stays available.
- Added source connector tests for official response parsing (mocked API), moderation/dedup/rate-limit rules, local HTTP ownership, DOM-safe rendering, opt-in auto-play and queue ordering. No account secrets were required for tests.
- Live/Discord official account integrations have **not** been verified against user-authorized live accounts: a user API Key/Bot Token and proper permissions are still required. REST polling is not Gateway/streamList low-latency delivery.

## 0.3.0.dev10 — Independent workspace modes with shared global TTS settings (2026-11-10)

- Redesigned the web application as seven workspaces: Studio, Document Reader, Live simulation, Discord simulation, Speech Queue/Subtitle, Shared Reading Rules and Shared Engine/Voice Settings. Each working mode has independent text and player state while Engine/Voice/DSP/Seed/Presets/Rules/Pronunciations remain centralized.
- Added exclusive local ModeState ownership: switching workspaces synchronously suspends all Browser audio, stops Reader auto-next, clears OBS PlaybackState and rotates per-mode playback tokens. Stale tabs and reports cannot overwrite the single local Overlay after switching.
- Added GET /v1/modes/state, POST /v1/modes/activate and bounded SSE GET /v1/modes/stream; Browser BroadcastChannel and HTTP Polling cover cross-tab and cross-browser fallback.
- Added persistent global Engine/Voice/Speed/DSP defaults (data/settings/global-voice.json, gitignored), optimistic revisions and GET/POST /v1/settings/global-voice. Existing Seed, Voice Presets and editable JSON reading rules stay shared.
- Studio now synthesizes via the shared Speech Job API and browser clock so it can drive OBS like Reader, Queue, Live and Discord simulations. Live/Discord are explicitly LOCAL text-input prototypes, not live integrations or connected bots.
- Kept original Document Reader, JSON Editor, manual alignment and waveform tools; added mode isolation, ownership, HTML structure, SSE, persistence and source-mode regression tests.
- The currently executing CPU inference cannot be force-interrupted by a tab switch: playback and pending autoplay stop immediately and cancellation is best effort. True YouTube Live/Discord adapters remain future milestones.

## 0.3.0.dev9 — Conservative Thai caption boundaries and narration chunking (2026-11-10)

- Fixed Estimated subtitles that cut Thai leading vowels, coda consonants and syllables into separate caption windows. The original roughly every-22-grapheme splitter now chooses only explicit punctuation/whitespace separators; if no natural separator exists, it retains the entire generated speech segment instead of claiming word boundaries.
- Changed the OBS overlay CSS to use native Thai line wrapping instead of forced overflow-wrap:anywhere; all text continues to use textContent (no HTML injection).
- Updated engine-neutral TXT/Markdown chunking to prefer natural separators and, only when a hard length limit has no separator, to try cutting before a Thai preposed vowel. Unavoidable Unicode-only fallback is disclosed by boundary_quality/start_boundary_quality in document chunk metadata and the Reader UI; dictionary-free chunking cannot guarantee Thai word boundaries in long unspaced prose.
- Shared the Unicode/Thai boundary checks with the Manual Alignment validator so user-created cues cannot isolate Thai preposed vowel marks.
- Incremented the document chunker revision used in the document_id hash to prevent old ordinal reading bookmarks from resuming at a wrong chunk after boundary changes. Previous document bookmarks must be re-selected/re-saved, but are not deleted.
- Added regression tests for Thai vowels, final consonants, punctuation/decimal numbers, emoji and deterministic chunk offsets. No language model, new dictionary, package or commercial asset was added.

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