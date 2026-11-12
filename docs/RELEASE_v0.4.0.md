# VoxWeaveTTS v0.4.0 — First Windows Portable Release

A self-contained Windows 10/11 x64 Thai speech studio, with a native Windows launcher, local Web UI and a bundled MakHam Paradee CPU ONNX voice.

## Download and start

Download **VoxWeaveTTS-v0.4.0-portable.zip** from this Release. Extract the *entire* `VoxWeaveTTS` folder to a writable location and double-click **VoxWeaveTTS.exe**.

The app starts a private HTTP server on **127.0.0.1:8765** and opens the system default browser (Firefox or Chrome). Keep the launcher open and use **Stop & Exit** to close it. A troubleshooting fallback, `Start-Console.cmd`, is included. No separate Python, Node, GitHub CLI or installer is required.

## Included features

- **Thai TTS out of the box** using the included MakHam Paradee INT8 CPU ONNX model and frozen dependencies. The external 325MB FastThaiG2P model is **not bundled**.
- Speech text input, TXT/Markdown document reader, pronunciation/rule editor, engine/voice speed and optional DSP controls, global settings, voice presets and audio/WAV generation.
- Per-workspace audio controls and a single-owner OBS Browser Source subtitle overlay.
- Live-read sources for **Discord Client RPC**, Discord Bot and YouTube Live using the user's own authorized credentials. Only the Discord Client connection was user-confirmed live before release; other providers were tested with simulated API responses.
- Shared serial chat speech queue, capped unread backlog, configurable read-message history, per-source settings Export/Import JSON.
- **Choose the export path** in Chrome (browser Save As) and Firefox (Windows Save As via loopback server). JSON profiles preserve all filled or empty fields, including Secret/Token values; Import never connects automatically.

## Security and licensing

- The server binds only to localhost. Do not forward its port to the public internet.
- Do **not** share exported profile JSONs: any API Keys, Bot Tokens and Client Secrets are plain text by request.
- This ZIP omits user-generated personal voices, tokens, custom settings, cached audio and the 325MB FastThaiG2P model.
- Application code is MIT. Bundled Python, ONNX dependencies and the MakHam Paradee voice have their **own** licenses, recorded under `THIRD_PARTY_NOTICES.txt`, Python `LICENSE.txt` and package metadata.
- Only an initial offline, fixed-voice CPU TTS model is bundled; this is **not** a voice cloning/training product. Other models must be checked for redistribution and commercial use separately.

## Compatibility and limitations

- Windows 10/11 **64-bit** (x64) with .NET Framework 4.x for the small launcher (console fallback uses only the included Python).
- Default browser: Firefox and Chrome supported.
- CPU synthesis. No native GPU fallback, automatic word-level alignment, voice cloning, model training or audio-hardware playback clock.
- Discord RPC requires approved app access and user consent. Live message integrations require network/provider credentials; they do not auto-connect.
- Tested relocated, self-contained runtime and MakHam Thai WAV synthesis on Windows, with Python and browser smoke tests. A completely fresh third-party Windows installation has not been independently certified.

**Installation guide (Thai/English):** [docs/PORTABLE.md](https://github.com/funggier/VoxWeaveTTS/blob/v0.4.0/docs/PORTABLE.md)

**SHA-256:** See the checksum in this Release's downloadable `SHA256SUMS.txt` attachment, and verify locally with `Get-FileHash`.
