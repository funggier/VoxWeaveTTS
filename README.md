# VoxWeaveTTS

**Portable Thai-first voice studio and real-time speech platform** — work in progress.

> **Current status (v0.1.0 foundation):** a working local text-processing HTTP API and preview page. **Voice synthesis, voice cloning, live Discord/YouTube connectors, subtitle event timing, and a bundled Windows portable executable are NOT implemented yet.** These are planned modules, not shipped capabilities.

## Goals

- Thai pronunciation overrides (e.g. `อมตะ`), with original subtitle spelling retained.
- User-defined spoken-word replacement, subtitle masking, skipped words, and inserted silence.
- Selectable voice profiles, expressive controls, model adapters and A/B audition.
- Live Discord / YouTube chat input with queueing and content filtering.
- Playback-clock-driven subtitle events for OBS Browser Source and external apps.
- Windows portable ZIP: all settings, voice references and model caches under a movable root, without forced writes to the system drive.

## Run the foundation prototype (Windows)

1. Install Python 3.11+ **for this development prototype only**.
2. Run `Start-Dev.cmd` from this directory. It uses only the Python standard library.
3. Open <http://127.0.0.1:8765/> in your browser.
4. Run `Test-Dev.cmd` to execute unit tests.

No external model downloads, microphone access, platform permissions or accounts are needed for this milestone.

## API

- `GET /v1/status` — build status and explicit capability flags.
- `GET /v1/rules` — locally stored replacement rules, if configured.
- `GET /v1/pronunciations` — locally stored pronunciation overrides, if configured.
- `POST /v1/text/process` — deterministic filter, replacement, silence and pronunciation processing.
- `GET /` — local HTML tester.

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
- [Architecture](docs/ARCHITECTURE.md)
- [API Contract](docs/API.md)
- [Portable distribution plan](docs/PORTABLE.md)
- [Roadmap](docs/ROADMAP.md)
- [Licensing and privacy](docs/SECURITY.md)
