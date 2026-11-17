# VoxWeaveTTS v0.10.0 — Native Universal v2, Verified Offline Runtime Pool & Trusted Provider SDK

**Windows 10/11 x64 · Python 3.11 bundled · Portable (extract then run) · Local-first Thai TTS**

This release moves to **native data-only `.vwmodel` format v2** and adds offline verified runtime installation plus independently approved Ed25519-signed external TTS adapters. No installer or Windows system Python is required to run the bundled MakHam model. Source, model archives and add-on runtime dependencies are separate artifacts with independent licenses.

## What's new

- **Native Universal `.vwmodel v2`:** The Model Package Manager uses v2 manifests, integrity checks, safe install/uninstall, and first-party trusted worker/adapter mappings without executing scripts supplied by archives. The included **MakHam Paradee v2** voice is preinstalled, and a matching v2 recovery archive is included. Previous `.vwmodel v1` archives are **not compatible**; install the new v2 packages.
- **Shared / isolated runtimes:** PyThaiTTS, Sherpa, Vachana, Kokoro and M2M100 worker families remain independently managed. Runtime health diagnoses relocation, missing Python, recipe drift, ABI mismatch and incomplete environments. Moving an extracted Portable folder may require a verified runtime rebuild.
- **Verified Wheelhouse Phase C:** Application-owned locks pin exact wheels, SHA-256, Python 3.11 ABI, Windows x64 and trusted dependency recipes. Local installation requires **explicit consent**, verifies every wheel snapshot, uses `uv --offline --no-index --require-hashes`, checks the final runtime path and rolls back failures. Sherpa, PyThaiTTS and M2M100 locksets have been tested with real isolated offline installations. Vachana/Kokoro remained test-only drafts pending dependency license review.
- **Trusted Provider Phase D:** Reviewed external TTS providers can use **Ed25519-signed** `provider.json`, `worker.py`, `requirements.txt`. Public publisher keys must be pinned and verified out-of-band, then executable code separately approved; changing or revoking a key disables the signed provider. The backward-compatible, manually reviewed SHA-pinned provider path remains available without signature. No `.vwmodel` can run package-supplied code.
- **Worker Protocol v1 SDK:** Reference `tts_provider_sdk.py` standard-library IPC server with bounded JSON Lines and PCM16 mono output, error redaction, and sample extension. The demo emits a synthetic test tone, not speech. `cryptography` is bundled with the Portable Core for signature verification.
- **Live queue, multilingual TTS, speech-error policy, translation, Discord/YouTube/TikTok integration** from recent development remain in place. Import/export user settings and model-rights constraints remain separate from source code.

## Files and installation

1. Download `VoxWeaveTTS-v0.10.0-portable.zip`; extract the whole directory to a writable folder, e.g. `T:\Apps\VoxWeaveTTS`. Do not run inside ZIP.
2. Start `VoxWeaveTTS.exe` (or `Start-Console.cmd`) and open `http://127.0.0.1:8765`. You should see **MakHam Paradee** in the Engine list. Local settings, cache, models, logs and output remain in that folder.
3. Additional `VoxWeaveTTS-*-format-v2.vwmodel` archives are **optional**; install via Model Packages tab. An installed model may need an appropriate isolated Runtime. Never import arbitrary untrusted executable files as model packages.
4. The optional `VoxWeaveTTS-*-win_amd64-py311-wheelhouse.zip` contains **only runtime dependencies** plus its trusted lock and notices (not model weights). Extract to the matching paths inside Portable; the Runtime Registry verifies SHA-256 on opt-in install. Do not use the Windows x64/Python 3.11 archives on other platforms.
5. For older user data, **back up your previous Portable folder** and import settings/models selectively. Do **not** overwrite older folders without a backup. v2 package IDs and storage paths differ from v1.

## Package and license matrix

| Model package | Kind / worker | License declarations | Important limitation |
|---|---|---|---|
| MakHam Paradee | Thai TTS / PyThaiTTS | Apache-2.0 upstream; dataset attribution | Preinstalled; rights to training data need independent review |
| FastThaiG2P ThaiSom | Thai TTS / PyThaiTTS | Apache-2.0 code/model declaration, dataset credits | Training/data/voice rights require review |
| Kokoro INT8 | Multilingual TTS / Kokoro | Apache-2.0 model declaration | Japanese eSpeak/phonemizer components include GPL obligations for redistribution |
| MeloTTS Chinese ONNX | Chinese TTS / Sherpa | MIT model declaration | Review training/voice rights separately |
| Supertonic 3 INT8 | Multilingual TTS / Sherpa | **OpenRAIL-M** | **Use restrictions**; not MIT despite MIT sample code; comply with full bundled license |
| Vachana Thai 4 Voices | Thai TTS / Vachana | MIT model declaration | Upstream `vachanatts` runtime wheel has unclear code license metadata; redistribution review ongoing |
| M2M100 418M | Translation / dedicated runtime | MIT model declaration | Experimental; actual translation was **not** reverified because Windows commit/pagefile pressure |

**No model is being certified as commercially cleared by VoxWeaveTTS.** Model weights, training datasets, runtime packages and the Core are separately licensed. Files marked NC/noncommercial, including Wayu NC, are **not included** in this commercial-safe-oriented release. Even other model licenses may have attribution, redistribution, source or use restrictions.

## Security and testing

- Untrusted Live chat, documents, model manifests and translation text remain **data**, never commands.
- Provider private signing keys are **not bundled**; trusting a public key does **not** approve executing its code. There is no OS-level sandbox for third-party Python code once approved.
- Portable is local HTTP `127.0.0.1:8765`, not a public remote service. Keep credentials in user settings; no user-specific passwords/tokens are inside release assets.
- Phase C isolated installation passed for Sherpa, PyThaiTTS, M2M100 and test-only draft Vachana/Kokoro. Relocation-repair test passed on one Windows machine; not yet reproduced on a different PC.
- M2M100 model inference with 418M weights remains **unverified due to prior Windows error 1455**; successful dependency installation does not prove successful translation. Do not alter your pagefile or kill unrelated processes just to run tests.
- This release includes complete source changes and documentation for Phase A/B/C and the **TTS-only** portion of Phase D. External STT / Voice Clone / LLM adapters, downloadable signed code marketplace and auto-key discovery are **not implemented**.

## Documentation

- `docs/UNIVERSAL_VWMODEL_V2_TH.md` — native model format
- `docs/MANAGED_RUNTIME_POOL_TH.md` — runtime pool and health
- `docs/VERIFIED_WHEELHOUSE_TH.md` — verified wheel dependencies
- `docs/WHEELHOUSE_LICENSE_REVIEW_TH.md` — dependency rights screening
- `docs/TRUSTED_PROVIDER_SDK_TH.md` — Ed25519 publisher trust and TTS Worker SDK

**Local development:** All runtime binaries and optional model packages are separate from tracked source. Release checksums are provided as SHA256SUMS; verify archives before using.
