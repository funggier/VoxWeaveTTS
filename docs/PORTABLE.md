# VoxWeaveTTS v0.6.0 — Windows Portable User Guide

**Status:** Windows 10/11 x64 portable release with concurrent Live/Discord workspaces, per-mode voice controls, queue policy, presets and model package management; not a voice-cloning suite. Tested with its relocated Python runtime and bundled MakHam Paradee CPU ONNX Thai voice. Other engines may require extra model packs and license review.

## Install and launch

1. Download `VoxWeaveTTS-v0.6.0-portable.zip` from https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.6.0.
2. Extract the **whole folder** to a writable location, for example `T:\Apps\VoxWeaveTTS`. Never run the EXE from inside the ZIP.
3. Double-click **VoxWeaveTTS.exe**. The small Windows launcher starts a local Python server, checks readiness, and opens your default browser (Firefox or Chrome). No Python, Node or system installation is needed.
4. Keep the launcher window open. The studio is at http://127.0.0.1:8765 and OBS Browser Source may use http://127.0.0.1:8765/overlay.
5. In the studio select the available **MakHam Paradee CPU** engine and try Thai TTS. For chat readers you must connect the appropriate authorized account/channel yourself.
6. To quit, choose **Stop & Exit** in the Windows launcher. It stops the backend it started. Do not open a second launcher for the same port.

**Fallback:** Run `Start-Console.cmd` if an unsigned new EXE is blocked by SmartScreen or the .NET Framework 4.x GUI is unavailable. The console launcher starts the same bundled Python server; open http://127.0.0.1:8765 manually and close the console to stop it.

## What ships

```
VoxWeaveTTS/
  VoxWeaveTTS.exe            Windows GUI launcher and Stop button
  Start-Console.cmd          Console alternative
  runtime/python/            Self-contained Python 3.11 and ONNX dependencies
  src/voxweavetts/           Local engine and API source
  web/                       Firefox/Chrome Web UI, OBS overlay
  models/makham-paradee/     Licensed MakHam INT8 model and config
  models/fastthaig2p/       Empty; Fast base model not bundled
  models/packages/         Empty; optional .vwmodel packages installed by user
  presets/                 Portable JSON voice presets (empty)
  data/                      Local settings, dictionaries, reading positions
  cache/                     Local temporary/model cache
  voices/                    Reserved for user-owned audio (empty)
  output/                    User-generated exports (empty)
  logs/                      Local diagnostics (empty)
  LICENSE                    MIT source code license
  THIRD_PARTY_NOTICES.txt    Runtime/model licenses and model SHA-256
  docs/                      Documentation and licensing notes
```

All app-generated settings, output and cache paths are relative to the extracted folder. The app binds to **127.0.0.1 only**. Do not forward port 8765 publicly: the local API does not provide remote authentication.

## AI Processing / Translation in v0.6.0

Open Settings → AI Processing to select **not translating**, **translation**, or **custom AI processing**. Translation language can be selected explicitly (Thai, English, Japanese, Chinese, Korean) or left unspecified for Ollama to follow Priority Instructions/Custom Prompt. With M2M100 and unspecified language, translation is skipped. Ollama is an **external, already-installed optional service** (default `http://127.0.0.1:11434`, configurable LAN IP/port); its model weights are not inside this ZIP. Local AI source text is sent to the configured Ollama service, which may be on a different LAN machine: review your privacy/network settings. Keep Alive retains the model in memory. Chat sender name/prefix and connector are not translated.

The M2M100 adapter is **experimental**, requires separately installed safetensors weights and Python dependencies (Torch, Transformers, SentencePiece, safetensors). It was tested locally but semantic quality was incorrect in some short cases, and is not suitable as an automatically trusted translator for public Live without further validation. [Optional M2M100 setup](M2M100_SETUP_TH.md) · [AI processing spec](AI_PROCESSING_TRANSLATION_TH.md).

Tool Calling and web search are **not included** in v0.6.0 and will be developed separately after this release.

## Optional Model Packages available separately

The main Portable ZIP still bundles **MakHam Paradee only**. The separately downloadable [Vachana 4-Voice and FastThaiG2P Thai Som packages](https://github.com/funggier/VoxWeaveTTS/releases/tag/modelpacks-v0.4.2) include pinned-source SHA-256 checksums and embedded licenses/attributions. Rights are as declared upstream (Vachana MIT; FastThaiG2P Apache-2.0 and Som TTS dataset CC BY 4.0), **not an independent audit of every training voice/data right**. Both optional models were tested using the exact v0.4.2 Portable runtime, without changing the main ZIP. See [Model Pack Catalog](../model-packs/README_TH.md).

## v0.4.4 YouTube LIVE streamList and quota protection

- YouTube LIVE prefers the official gRPC liveChatMessages.streamList and receives messages on an open push stream. The bundled runtime includes grpcio and protobuf. REST fallback is paced at 30 seconds minimum.
- quotaExceeded / dailyLimitExceeded stop automatic retries; temporary rateLimitExceeded backs off and ambiguous gRPC RESOURCE_EXHAUSTED stops automatic reconnect until quota is checked.
- streamList still consumes API quota at stream startup; invalid API keys and provider permissions are not bypassed.
- Vachana 4 Voices and FastThaiG2P Thai Som are separate optional .vwmodel assets on the same GitHub Release page, not embedded in the main ZIP.
## v0.4.3 reconnect fix and optional model downloads

- Clicking Connect for YouTube LIVE or Discord now reclaims a fresh owner token for just that workspace after backend restarts or tab takeovers, without disconnecting unrelated channels.
- HTTP 400/401/403/404 from YouTube or Discord now report categories to help diagnose credentials, quota, permissions or unavailable channels.
- Vachana 4 Voices and FastThaiG2P Thai Som .vwmodel archives are separate assets on the v0.4.4 Release page alongside the Portable ZIP. They include original license and attribution documentation; MakHam remains the only bundled model.
## What changed in v0.4.2

- All Live/Discord sources can stay connected while switching to other workspaces. Choose **serial** (one voice at a time) or **overlap** playback in the top bar.
- Each workspace independently selects Engine/Voice, playback speed (x0.60–x5.00), gain/pitch/bass/treble (0.01 steps), Formant Preserve and seed; the next speech job picks up changes.
- Voice Presets save as individual `.json` files in `presets/`; copied files show in each dropdown after refresh. Model packs install separately through **ตั้งค่า > Model Packages**.
- YouTube LIVE, TikTok LIVE, Discord Bot and Discord Client each have an independent **อ่านชื่อผู้ส่งก่อนอ่านข้อความ** setting, off by default, exported with their source settings JSON. Audio failures pause auto-read instead of silently unchecking it.
- Only MakHam Paradee weights are bundled. Vachana/FastThaiG2P packs are *not* attached to this public release pending complete redistribution-rights and dependency verification.

## TikTok LIVE (TikFinity Desktop required)

- Install and connect **TikFinity Desktop** on the same PC to your TikTok livestream.
- Open VoxWeaveTTS **TikTok LIVE**, then click **เชื่อม TikFinity** using `ws://localhost:21213/`.
- Receive only chat messages: the shared serial TTS queue, filters, read-history limit and OBS captions are available; gifts and likes are ignored.
- No TikTok credentials or cookies are requested. This uses a third-party **local event bridge**, not an official public TikTok LIVE API. No TikFinity package or unofficial TikTok scraping libraries are bundled.
- TikTok/TikFinity live account receipt has not yet been validated in real conditions; the local WebSocket mock tests passed. See [Thai instructions](TIKTOK_LIVE_TH.md).

## Discord, YouTube, secrets and profiles

- Discord Client Reader requires Discord Desktop, a Developer Application with permitted `rpc` / `messages.read` scopes, the correct Channel ID and explicit consent. The user has confirmed message reading with the dev17 implementation; this initial portable package uses the same local RPC code.
- Discord Bot Reader uses an authorized bot token and Discord's official REST API. YouTube Live uses your own API Key. These two integrations have mock coverage but have not been verified against an authorized live account in this release.
- Profile **Export / Save As** opens a file chooser in Chrome and a Windows file chooser via the local backend in Firefox. **Import** re-fills fields, including blank fields and credentials; it never connects on its own.
- **IMPORTANT:** JSON profile files contain your **API Keys / Bot Tokens / Client Secrets in plain text** if entered before export. Never publish them to GitHub, chats or public clouds.
- Source connectivity and streaming voice are independent of local synthesis. Live source connection still requires the appropriate provider/network access.

## Troubleshooting

- **Port already in use:** Close an existing VoxWeaveTTS server or another application using port 8765, then relaunch. One local server per port.
- **Browser did not open:** Click *Open App* or visit http://127.0.0.1:8765.
- **Missing/disabled engine:** Select MakHam Paradee; FastThaiG2P 325MB model is intentionally not bundled. On another machine, verify the entire ZIP was extracted.
- **No audio plays:** Ensure the selected engine has `assets_ready` and `runtime_ready` in the Web UI. Browsers may require a first user click before auto-play is permitted.
- **Firefox Export:** the Windows native Save As dialog appears from the locally running backend. It may be behind another window. The user must choose a destination; cancel creates no file.
- **Moving the app:** Close it, move the entire folder (not only `.exe`), relaunch. Keep and back up `data/`, `models/` and `voices/` on upgrades. Avoid overwriting user directories when extracting a newer release.
- **Missing Windows runtime:** Windows 10/11 x64 with .NET Framework 4.x is required by the small GUI launcher. The bundled Python backend and console fallback do not require .NET; they rely on the Windows OS C runtime.

## Model and redistribution licenses

The VoxWeaveTTS application source is MIT, while MakHam Paradee, PyThaiTTS, Python, NumPy, ONNX Runtime, PyThaiNLP and dependencies retain their separate upstream licenses and notices. The bundled MakHam checkpoint uses the Apache-2.0 model metadata published by PyThaiNLP (https://huggingface.co/pythainlp/MakHamTTS). See `THIRD_PARTY_NOTICES.txt`, included Python/`*.dist-info` license files and [commercial policy](COMMERCIAL_LICENSE_POLICY_TH.md).

The package **does not contain** personal recordings, login tokens, user-generated data, the 325MB Fast model or unreviewed noncommercial models. Commercial deployment or resale still requires checking user content rights, dependencies and updates; a public Release is not a legal certification.

## Release verification

Compare the downloaded ZIP's SHA-256 with the hash in the GitHub Release notes. On PowerShell:

```powershell
Get-FileHash .\VoxWeaveTTS-v0.4.3-portable.zip -Algorithm SHA256
```

Source: https://github.com/funggier/VoxWeaveTTS
