# VoxWeaveTTS

**Portable Thai-first voice studio and real-time speech platform** — work in progress, currently at M1 CPU audio preview.

> **Current status (v0.2.0.dev2 M1 preview):** local text processing and **real Thai WAV generation** using PyThaiTTS/FastThaiG2P CPU ONNX, when the optional model/runtime are installed. **Voice cloning, voice-specific tuning beyond speed, live Discord/YouTube connectors, subtitle playback events, and a bundled Windows portable executable are NOT implemented.**

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
3. Open <http://127.0.0.1:8765/> and click **สร้างเสียง WAV** to synthesize and audition Thai speech; no voice cloning in this engine. For words such as `ฮ่า ฮ่า ฮ่า` that vary across stochastic runs, change the **Seed** and save a preferred value. The engine now uses a fresh ONNX session per speech request to reproduce the same audio for a fixed text/speed/seed on the tested runtime.
4. Use `scripts/Generate-ThaiSample.ps1` while the local server is running to save `output/api_demo.wav`.
5. Run `Test-Dev.cmd` for unit tests.

The Python `.venv` is a developer environment, **not the final portable executable**. Offline synthesis works once the engine and model are installed.

## API

- `GET /v1/status` — build status and explicit capability flags.
- `GET /v1/rules` — locally stored replacement rules, if configured.
- `GET /v1/pronunciations` — locally stored pronunciation overrides, if configured.
- `POST /v1/text/process` — deterministic filter, replacement, silence and pronunciation processing; optional `match_mode: five_run` safely maps repeated chat 5s to speech while retaining the original subtitle.
- `GET /v1/engines` and `GET /v1/voices` — available backend/capabilities and fixed voice.
- `POST /v1/speech` — generate Thai PCM16/WAV through the optional FastThaiG2P CPU backend (500 spoken characters max per request), with optional reproducible `seed`.
- `GET/POST /v1/settings/synthesis` — view/store a preferred seed in local portable settings (POST requires an explicit intent header).
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