# VoxWeaveTTS v0.4.1 — TikTok LIVE Reader for Windows Portable

Adds an independent **TikTok LIVE** reader with the same Thai TTS, shared pronunciation settings, FIFO audio queue, OBS subtitle synchronization and read-history controls as the existing YouTube and Discord readers.

## Download and start

Download **VoxWeaveTTS-v0.4.1-portable.zip**, extract the full folder to a writable location, then run **VoxWeaveTTS.exe**. Windows 10/11 x64, Firefox or Chrome. The included Windows launcher and bundled Python/MakHam Paradee CPU ONNX engine do not require separate Python, Node, or installation.

## TikTok LIVE setup

1. Install **TikFinity Desktop** separately from https://tikfinity.zerody.one/.
2. Connect TikFinity to a TikTok LIVE you are authorized to access; TikFinity must run on the same computer.
3. In VoxWeaveTTS select **TikTok LIVE**, use `ws://localhost:21213/` and click **เชื่อม TikFinity**.
4. Send a new chat message to the active LIVE and verify that it appears and enters the speech queue. Keep VoxWeaveTTS's browser and TikFinity open during the stream.
5. Profile **Export / Save As** and **Import** work in Firefox and Chrome; importing fills editable settings but does not auto-connect.

**TikTok account credentials are never requested by VoxWeaveTTS**. Only chat comments are spoken; gifts, likes, follows and other stream events are ignored.

### Important limitation

This is **not a direct official TikTok LIVE API integration**. TikTok has no general public LIVE chat API documented for ordinary developers. The feature reads the **local TikFinity Desktop Event API**, which is a third-party service and has its own availability/terms. A real TikFinity/TikTok LIVE connection was **not available during this build** and is unverified; automated WebSocket and TTS queue tests passed with simulated chat. TikFinity must be installed separately, and any authorization or service issues must be resolved with that provider.

## Other included features

- Ready-to-use Thai voice synthesis with **MakHam Paradee** bundled CPU model; native speed and shared speech rules/presets
- Document reader, Live/Discord inputs, Discord Desktop RPC, per-source filters, auto-read, bounded voice queues and capped read-message history
- Firefox/Chrome profile Save As and Import with optional blanks; credentials in other source profiles are saved in plaintext if exported, so store them privately
- Browser-driven OBS subtitles and exclusive playback ownership across 9 workspaces
- Source code, docs, and Windows portable build script

## Verification and licenses

- Python 161 unit tests and JavaScript smoke test suites, including TikTok mock WebSocket connection, chat-only filtering, duplicate handling, local URL validation, disconnect cleanup, global TTS queue and profile round-trips.
- Portable ZIP extraction, bundled Thai WAV synthesis and local HTTP TTS smoke tests use the self-contained Python runtime, not the developer's venv.
- No TikFinity binaries, unofficial TikTok scraping libraries, TikTok cookies or credentials, the large FastThaiG2P model, user voices or user settings are packaged.
- VoxWeaveTTS code is MIT; MakHam Paradee/PyThaiTTS and dependencies retain their respective licenses and notices in `THIRD_PARTY_NOTICES.txt`. Third-party TikFinity and TikTok usage may be subject to separate conditions.
- No Voice Cloning, training, native hardware playback clock or fully automated word-level subtitle alignment in this release.

**Guide:** https://github.com/funggier/VoxWeaveTTS/blob/v0.4.1/docs/TIKTOK_LIVE_TH.md

**SHA-256:** See the attached `SHA256SUMS.txt`. Verify the archive using Windows PowerShell `Get-FileHash`.
