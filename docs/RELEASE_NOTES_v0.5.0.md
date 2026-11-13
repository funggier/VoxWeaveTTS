# VoxWeaveTTS v0.5.0 — Live Chat, Configurable Speech and TikTok Extension (Windows Portable)

This release includes the development work since v0.4.4. It supports Windows 10/11 x64 and includes the bundled **MakHam Paradee ONNX CPU** Thai voice, embedded Python runtime, voice and pronunciation settings, local speech API, OBS subtitle integration, and the new LIVE readers.

## What's new

- **YouTube LIVE (API)** retains the official API + gRPC streamList fallback. **YouTube LIVE (Browser)** is a separate experimental chat-only Chrome/Edge DOM reader that does not require a YouTube Data API key (not an official YouTube integration).
- **TikTok LIVE (Extension)** reads new *text comments only* from the user-selected Chrome LIVE tab with a manually installed Manifest V3 extension. It uses temporary local pairing, no automated Chrome login, no CDP, and a localhost-only bridge. Extension version **0.2.4** is included in the main Portable ZIP and also offered as a separate ZIP.
- **TikTok LIVE (TikFinity)** continues to read text chat via its local WebSocket.
- **Removed gift reading** from both TikTok modes. No gift reading switch or gift speech settings remain in the UI; incoming Gift events are ignored, including events forwarded from an older extension. Live follows, joins, shares, and likes are not speech inputs.
- **Configurable speaker wording** separately for each source: optionally read the sender name, set a sender prefix such as `คุณ`, and set an independent phrase such as `พิมพ์ว่า`.
- **YouTube sender `@` control:** optionally speak the leading `@` in a YouTube handle; leaving it off only changes the spoken sender name and does not modify `@` inside viewer comments. A previously configured **global replacement rule** for `@` still applies until you disable that rule.
- **Comment extraction and visibility diagnostics:** TikTok Extension handles varying badge/rank displays and background-tab DOM updates more robustly and reports chat DOM status. Actual coverage still depends on what TikTok renders.

## Downloads

- `VoxWeaveTTS-v0.5.0-portable.zip` — main Windows Portable app, MakHam Paradee, web UI, and `extensions/tiktok-live-connector` to load unpacked.
- `VoxWeaveTTS-TikTok-Extension-v0.2.4.zip` — optional standalone copy of the same Chrome Extension for easier installation.
- `SHA256SUMS-v0.5.0.txt` — SHA-256 hashes for these ZIP assets.

Optional **Vachana Thai 4 Voices** and **FastThaiG2P Thai Som** model packages remain available on the [v0.4.4 release](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.4.4). The main ZIP includes only MakHam Paradee by default.

## Quick start

1. Extract the entire Portable ZIP into a writable folder such as `T:\Apps\VoxWeaveTTS`. Do not run the EXE directly from the ZIP.
2. Launch `VoxWeaveTTS.exe` (or `Start-Console.cmd`).
3. Open `http://127.0.0.1:8765/` and select the desired TTS engine/mode.
4. For TikTok LIVE (Extension), in Chrome open `chrome://extensions`, enable Developer mode, and use **Load unpacked** to choose `extensions/tiktok-live-connector` from the unpacked app folder. Open the intended TikTok LIVE tab, generate a pairing code in the app, and connect using the extension popup.
5. After upgrading an already-installed extension, **Reload it in `chrome://extensions`, refresh the TikTok LIVE tab, restart the app, and pair again**.
6. Expand **กำหนดการอ่านข้อความและข้อมูลพิเศษ** to choose automatic reading, sender name and sender prefix, connector phrase, and comment reading. No Gift options are provided.

## Important limitations

The Chrome extension is a development integration and is not endorsed by TikTok. It can read comments only if TikTok provides them in the selected tab's DOM; background-tab throttling or platform layout changes can affect delivery. TikTok and YouTube automated access may be restricted under their service terms; use only where authorized. Gift announcements are **not supported** in v0.5.0.

The older voice, model, and subtitle features remain; no voice cloning/training is included. Review bundled third-party notices and the optional model-pack licenses before redistributing models or using them commercially.
