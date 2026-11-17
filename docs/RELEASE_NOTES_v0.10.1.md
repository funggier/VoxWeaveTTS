# VoxWeaveTTS v0.10.1 — Native Universal v2 + Wayu NC 12 Voices, Verified Offline Runtimes & Trusted Provider SDK

**Windows 10/11 x64 · Python 3.11 bundled · Portable (extract then run) · Local-first Thai TTS**

This release adds **Wayu Paxa Edge Thai/English, 12 voices**, as a separately downloadable **CC BY-NC 4.0 / NonCommercial-only** native-v2 package (not bundled in the base Portable ZIP). It retains the Native `.vwmodel v2` model system, verified offline runtime installation and separately approved Ed25519-signed external TTS adapters introduced in v0.10.0. No installer or Windows system Python is required to run the bundled MakHam model. Source, model archives and add-on runtime dependencies are separate artifacts with independent licenses.

## New in v0.10.1 — Wayu NC Native v2

- **Wayu Paxa Edge NC (12 original voices, Thai + English):** Optional `VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0-format-v2.vwmodel` package. Automatically labeled `[NC / NonCommercial]` in the engine list, with `commercial_status=hold`. **Commercial use is NOT permitted under CC BY-NC 4.0.**
- **Exact pinned upstream binaries:** One original `model.pth`, 12 voice `.pt` files, and `config.json` have fixed first-party SHA-256 digests. V2 permits serialized PyTorch only for this exact Wayu ID/version and no other package. File hashes are checked before install and again by the isolated Worker before inference. License/source revision cannot be replaced by user-supplied metadata.
- **Wayu native engine verified:** Installed into the v2 registry with all 12 selectable voices and th/en, the separate existing `wayu-nc` runtime reported ready, and a real Thai synthesis through the Wayu Worker produced 63,600 PCM16 bytes.
- **Important runtime limitation:** Wayu's dependencies include Git/direct-URL requirements; **there is no Verified Offline Wheelhouse for Wayu NC**. Installing the isolated Worker on a new PC may require internet access and the pinned third-party dependency sources. Install model via Model Packages and, if necessary, run `scripts/Install-WayuWorker.ps1` explicitly.
- **Upstream license and acceptable-use:** https://huggingface.co/wayu-ai/wayu-paxa-tts-edge · https://creativecommons.org/licenses/by-nc/4.0/legalcode.en · https://www.wayuresearch.org/terms#acceptable-use. Model weights unchanged; legal attribution and upstream terms are embedded in the archive. No endorsement by the original authors.
- **Full updated release:** Windows Portable, 8 native-v2 packages, 3 independently downloaded offline wheelhouses (Sherpa, PyThaiTTS, M2M100), source, documentation, TikTok extension and SHA256SUMS.

## v0.10.0 features retained

- **Native Universal `.vwmodel v2`:** The Model Package Manager uses v2 manifests, integrity checks, safe install/uninstall, and first-party trusted worker/adapter mappings without executing scripts supplied by archives. The included **MakHam Paradee v2** voice is preinstalled, and a matching v2 recovery archive is included. Previous `.vwmodel v1` archives are **not compatible**; install the new v2 packages.
- **Shared / isolated runtimes:** PyThaiTTS, Sherpa, Vachana, Kokoro and M2M100 worker families remain independently managed. Runtime health diagnoses relocation, missing Python, recipe drift, ABI mismatch and incomplete environments. Moving an extracted Portable folder may require a verified runtime rebuild.
- **Verified Wheelhouse Phase C:** Application-owned locks pin exact wheels, SHA-256, Python 3.11 ABI, Windows x64 and trusted dependency recipes. Local installation requires **explicit consent**, verifies every wheel snapshot, uses `uv --offline --no-index --require-hashes`, checks the final runtime path and rolls back failures. Sherpa, PyThaiTTS and M2M100 locksets have been tested with real isolated offline installations. Vachana/Kokoro remained test-only drafts pending dependency license review.
- **Trusted Provider Phase D:** Reviewed external TTS providers can use **Ed25519-signed** `provider.json`, `worker.py`, `requirements.txt`. Public publisher keys must be pinned and verified out-of-band, then executable code separately approved; changing or revoking a key disables the signed provider. The backward-compatible, manually reviewed SHA-pinned provider path remains available without signature. No `.vwmodel` can run package-supplied code.
- **Worker Protocol v1 SDK:** Reference `tts_provider_sdk.py` standard-library IPC server with bounded JSON Lines and PCM16 mono output, error redaction, and sample extension. The demo emits a synthetic test tone, not speech. `cryptography` is bundled with the Portable Core for signature verification.
- **Live queue, multilingual TTS, speech-error policy, translation, Discord/YouTube/TikTok integration** from recent development remain in place. Import/export user settings and model-rights constraints remain separate from source code.

## Files and installation

1. Download `VoxWeaveTTS-v0.10.1-portable.zip`; extract the whole directory to a writable folder, e.g. `T:\Apps\VoxWeaveTTS`. Do not run inside ZIP.
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
| Wayu Paxa Edge NC (12 voices) | Thai/English TTS / isolated Wayu Worker | **CC BY-NC 4.0 — NonCommercial ONLY** | **No commercial use**. Runtime uses Git/direct-URL dependencies; no offline wheelhouse. Original weights pinned and acceptable-use terms enclosed |
| M2M100 418M | Translation / dedicated runtime | MIT model declaration | Experimental; actual translation was **not** reverified because Windows commit/pagefile pressure |

**No model is being certified as commercially cleared by VoxWeaveTTS.** Model weights, training datasets, runtime packages and the Core are separately licensed. Wayu NC is an **explicitly labeled separate optional download in this release**, but is **not bundled in the base Portable ZIP** and must **never be used commercially** under the CC BY-NC 4.0 terms. Even other model licenses may have attribution, redistribution, source or use restrictions.

## Security and testing

- Untrusted Live chat, documents, model manifests and translation text remain **data**, never commands.
- Provider private signing keys are **not bundled**; trusting a public key does **not** approve executing its code. There is no OS-level sandbox for third-party Python code once approved.
- Portable is local HTTP `127.0.0.1:8765`, not a public remote service. Keep credentials in user settings; no user-specific passwords/tokens are inside release assets.
- Phase C isolated installation passed for Sherpa, PyThaiTTS, M2M100 and test-only draft Vachana/Kokoro. Relocation-repair test passed on one Windows machine; not yet reproduced on a different PC.
- M2M100 model inference with 418M weights remains **unverified due to prior Windows error 1455**; successful dependency installation does not prove successful translation. Do not alter your pagefile or kill unrelated processes just to run tests.
- This release includes complete source changes and documentation for Phase A/B/C and the **TTS-only** portion of Phase D, plus Wayu NC native-v2 compatibility. External STT / Voice Clone / LLM adapters, downloadable signed code marketplace and auto-key discovery are **not implemented**.

## Documentation

- `docs/UNIVERSAL_VWMODEL_V2_TH.md` — native model format
- `docs/MANAGED_RUNTIME_POOL_TH.md` — runtime pool and health
- `docs/VERIFIED_WHEELHOUSE_TH.md` — verified wheel dependencies
- `docs/WHEELHOUSE_LICENSE_REVIEW_TH.md` — dependency rights screening
- `docs/TRUSTED_PROVIDER_SDK_TH.md` — Ed25519 publisher trust and TTS Worker SDK
- `docs/WAYU_NC_NATIVE_V2_TH.md` — Wayu NC v2 installation, source pins and legal restrictions

**Local development:** All runtime binaries and optional model packages are separate from tracked source. Release checksums are provided as SHA256SUMS; verify archives before using.