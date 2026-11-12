# VoxWeaveTTS v0.4.4 — YouTube LIVE streaming + quota-aware reader

Windows 10/11 x64 Portable release with **YouTube LIVE `liveChatMessages.streamList` over gRPC** and the previously released multichannel TTS functionality. Optional Thai model packs are **separate selectable download assets in this same Release**.

## Download assets

| File | Included voices / contents | Source-declared rights |
|---|---|---|
| `VoxWeaveTTS-v0.4.4-portable.zip` | Portable app and embedded MakHam Paradee CPU ONNX; Python, grpcio, protobuf, UI, local API, OBS overlay | Source program MIT; bundled MakHam model Apache-2.0 |
| `VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel` | Four Thai voices (2 female, 2 male) | VIZINTZOR's VachanaTTS model card declares MIT; training/voice rights not independently audited |
| `VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel` | Kokoro Thai Som voice | awslabs/FastThaiG2P Apache-2.0 with upstream NOTICE; Som TTS training dataset declared CC BY 4.0 |
| `SHA256SUMS-v0.4.4.txt` | SHA-256 digests of all three downloads | Integrity checks |

The main Portable ZIP includes **MakHam only**. Model pack archives have pinned source asset checksums in their manifests, `legal/license.txt` and `legal/attribution.md`; FastThaiG2P additionally has `legal/notice.txt`.

**Redistribution conditions:** Follow the actual publisher's license and attribution requirements. VoxWeaveTTS does not certify every speaker, dataset or training-right claim, does not provide a commercial-rights warranty, and cannot waive underlying third-party license requirements. Users must review any remaining rights uncertainty.

## What's new in v0.4.4

- **YouTube gRPC push streaming**: Uses official `liveChatMessages.streamList` rather than repeatedly issuing `liveChatMessages.list` HTTP requests. Keeps the continuation token to resume after a stream interruption, does not read pre-connection history as new speech, and supports clean Stop/disconnect.
- **Conservative REST fallback**: If the gRPC transport is unavailable or the service responds as unimplemented, uses REST `liveChatMessages.list` with a minimum 30-second interval, respecting longer provider guidance. Neither transport has zero quota cost.
- **Quota-aware errors**: Whitelisted Google error reasons distinguish `quotaExceeded`, `dailyLimitExceeded`, and `rateLimitExceeded` without exposing raw error bodies, URLs containing API keys, or credentials. Confirmed daily quota exhaustion stops automatic requests. Temporary rate limits back off; ambiguous gRPC `RESOURCE_EXHAUSTED` stops automatic reconnects for safety.
- **Per-source status**: The YouTube LIVE source status identifies whether the active transport is `streamList` or REST polling.
- **Bundled dependencies**: Python runtime now includes `grpcio` and `protobuf` with their upstream license information in `THIRD_PARTY_NOTICES.txt` and installed package metadata.

Retained from v0.4.3: concurrent YouTube/TikTok/Discord modes, serial or overlapping speech policy, independent voice and sender-name controls, saved JSON presets, OBS overlay, Model Package Manager, and refreshed owner token on explicit Connect.

## Install

1. Download `VoxWeaveTTS-v0.4.4-portable.zip`. Extract the entire archive to a **writable directory**, not inside the ZIP.
2. Run `VoxWeaveTTS.exe` (or `Start-Console.cmd` as a fallback) and open http://127.0.0.1:8765/ in Firefox or Chrome.
3. Choose the MakHam Paradee engine to test Thai speech. For other voices, download the desired `.vwmodel` asset separately, then install via **ตั้งค่า → จัดการ Model Packages → ติดตั้ง Model Package (.vwmodel)**. The same package ID/version is not overwritten automatically; uninstall the previous pack before replacing it, after backing up needed files.
4. To read YouTube comments, use a **valid YouTube Data API v3 key** and currently accessible live video/chat ID, then explicitly click Connect. Provider API quotas and permissions still apply.

When upgrading, back up `data/`, `presets/` and `models/packages/` before copying files. Never upload an exported source profile containing API keys, Bot Tokens or Client Secrets.

## Verification and limitations

- Local Python regression suite: **197 tests passed**.
- JavaScript UI/queue smoke tests: **17 suites passed**.
- Local gRPC server with synthetic Thai messages: passed. No user's Google credentials or quota were consumed during these tests.
- Windows Portable archive extracted and verified; MakHam Thai WAV generated through embedded runtime and local HTTP speech endpoint. Optional Vachana/FastThaiG2P packs were tested with v0.4.3 compatible embedded runtime, with unchanged source-pinned model weights.
- GitHub Actions: Python 3.11, 3.13 and JavaScript test jobs verified before publication.
- User reported that the development streaming mode worked. This is **not** a guarantee that every live chat, API key or quota state will work. A successfully opened stream may still consume quota and terminate when quota is exhausted.

More details: [Portable Guide](https://github.com/funggier/VoxWeaveTTS/blob/v0.4.4/docs/PORTABLE.md) · [Live Sources (Thai)](https://github.com/funggier/VoxWeaveTTS/blob/v0.4.4/docs/LIVE_INPUT_ADAPTERS_TH.md) · [Models & Licenses](https://github.com/funggier/VoxWeaveTTS/blob/v0.4.4/model-packs/README_TH.md)

Source: https://github.com/funggier/VoxWeaveTTS
