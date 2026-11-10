# VoxWeaveTTS

**Portable Thai-first voice studio and real-time speech platform** — work in progress, currently at M1 CPU audio preview.

> **Current status (v0.3.0.dev3 Engine-Neutral Reader preview):** local text processing and **real Thai WAV generation with two CPU ONNX Engines**, FastThaiG2P and MakHam Paradee, when the optional model/runtime are installed. **Voice cloning/fine-tuning, native expressive controls, live Discord/YouTube connectors, subtitle playback events, and a bundled Windows portable executable are NOT implemented.** The preview now offers native Speed plus optional post-DSP Pitch, Gain, Bass and Treble.

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
- Versioned job events; no claim of playback/OBS synchronization yet.
- All engines retain `commercial_status: review_required` unless their complete artifact and dependencies pass an audit.

See [Engine-Neutral Core architecture (Thai)](docs/ENGINE_NEUTRAL_CORE_TH.md).

## Readable Rules / Pronunciations JSON editor

The existing **Rules JSON array** and **Pronunciations JSON object** now provide format, syntax/type check, download and quick-entry actions. Quick entry uses JSON.stringify to escape quotation marks, backslashes and Unicode safely. Formatting preserves the rule array's order. **Save in Program** now persists validated config under ignored local `data/filters/rules.json` and `data/dictionaries/pronunciations.json`; saved rules reload on app start and are shared by all Engines. The editor also supports importing previously exported JSON files. Concurrency is protected by section-specific SHA-256 revisions (HTTP 409 on conflict), and file downloads remain separate from server persistence. See [Thai JSON pronunciation guide](docs/PRONUNCIATION_JSON_TH.md).

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