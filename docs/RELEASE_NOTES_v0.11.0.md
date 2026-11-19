# VoxWeaveTTS v0.11.0 — Universal v3 Offline Portable

**Windows 10/11 x64 · Python 3.11 bundled · 100% offline .vwmodel v3 package installation**

This is a **major package compatibility break**, not an in-place update for v0.10.3. Existing v1/v2 model packages are **not accepted**. Extract the new Portable into a **new folder**, then install only v3 model packages. This release does not automatically delete user files or convert old packages.

## Main changes

- Single-file `.vwmodel v3` contains weights, capabilities, legal rights, provenance, SHA-256 file index and (where needed) *all* dependency wheels and their lock.
- Two-phase native Windows file picker: **preview package and rights → explicit consent → install**. No network requests, package hooks, dynamic Python code or license server are used in the installer. Additional acknowledgement for NonCommercial model terms.
- Per-package isolated relocatable dependencies in `runtime/environments/` using a verified content fingerprint. Shared runtime is removed **only after the final model using it is uninstalled**.
- Core MakHam Paradee is preinstalled and its v3 recovery file is included in the Portable. The main app does not ship optional large models or personal voice files.
- Retired old v2 runtime installers/repair flows, model-package reader and v1/v2 install endpoints. No automatic repair. Use uninstall/reinstall with the same complete offline package instead.
- Portable Doctor reports runtime integrity, missing dependencies, relocated installations and mismatched model hashes without modifying data.
- Fixed M2M100 worker launch and log lifecycle, safer error handling, and v3-only UI/status text. Retained existing Thai TTS, translation, multilingual routes, live sources, queue and overlays.

## Release files

- `VoxWeaveTTS-v0.11.0-portable.zip`: self-contained Windows Portable, embedded Python, program, TikTok extension folder and preinstalled MakHam v3. Run `VoxWeaveTTS.exe` or `Start-Console.cmd`. Default local address `http://127.0.0.1:8765/`; avoid conflicting with an already running instance.
- `VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0-format-v3.vwmodel`: separate recovery for bundled MakHam.
- `VoxWeaveTTS-fastthaig2p-thai-som-0.3.0-format-v3.vwmodel`: Thai Som ONNX (Apache-2.0 declared by upstream; training dataset attribution).
- `VoxWeaveTTS-melo-chinese-onnx-1.0.0-format-v3.vwmodel`: Mandarin and English ONNX (upstream model-card MIT; voice/data rights still require review).
- `VoxWeaveTTS-supertonic3-multilingual-int8-1.0.0-format-v3.vwmodel`: 31-language INT8 ONNX, original **OpenRAIL-M with use-based restrictions**, *not MIT*.
- `VoxWeaveTTS-m2m100-418m-1.0.0-format-v3.vwmodel`: experimental M2M100 translation model + all pinned runtime wheels (upstream MIT). Requires substantial free RAM/Windows commit memory; no automatic translation-quality guarantee.
- `CATALOG-v3.json` and `SHA256SUMS-v0.11.0.txt`: verification metadata and release file checksums.
- `VoxWeaveTTS-TikTok-Extension-v0.2.5.zip`: extension archive supplied separately for manual installation.

**Not included in v3 release:** Wayu Paxa Edge NC, Vachana and Kokoro legacy v2 model packages or their previously separate runtime installers. They are not convertible simply by renaming a filename. Wayu remains NonCommercial-only. The v3 framework is designed to accept reviewed future model packages.

## Offline installation steps

1. Extract the entire Portable ZIP to a fresh folder (e.g. `T:\\Apps\\VoxWeaveTTS`). Do not run it directly from inside the ZIP.
2. Run `VoxWeaveTTS.exe`. Confirm MakHam is visible and ready.
3. Download the desired `-format-v3.vwmodel` file **once** and copy it anywhere on the offline computer.
4. In **Model Package Manager**, select the file, read the license/attribution prompt and confirm. The program checks the file SHA-256 and installs its approved dependencies from the package itself. Internet access is not needed, and no external dependency download is permitted.
5. If an installed runtime becomes invalid, uninstall the affected model package(s), then reinstall the original complete file. Do not copy or reuse v2 runtime folders.

When migrating from an older release, first back up personal data, dictionaries, presets, profiles and settings. Import or selectively copy only their user-data locations into a fresh v3 Portable. Preserve the v2 installation intact as a rollback option; **do not copy `models/universal/v2`, old `runtime`, `src`, `web`, `scripts` or executable files over v3**.

## Validation summary

- Python test suite: **441 tests passed** on Windows development environment; JavaScript browser tests: **35 passed**.
- Windows Portable v3 staging build completed; built-in Python passed deep package integrity verification, MakHam produced PCM WAV at 24 kHz.
- FastThaiG2P v3 archive installed fully offline with its Python wheel runtime and produced actual Thai PCM WAV at 24 kHz.
- **Real relocation test:** moved the complete Portable to a different directory, reused the isolated FastThai Runtime without reinstalling, generated actual Thai WAV and restored QA stage successfully.
- Supertonic v3 installed fully offline and produced actual English PCM WAV at 44.1 kHz. Melo Chinese shared that approved Sherpa runtime; removing one did not remove the runtime still used by the other; removing the final package did.
- **M2M100 v3 installed fully offline**, but real translation inference was **not completed** on the reference Windows machine because the memory/commit preflight rejected launch. The application did not terminate Ollama or change Windows paging settings. On machines with adequate commit headroom, translation correctness still requires independent evaluation.
- Five v3 archives have passed full SHA-256 streaming checks of their indexed contents, pinned native weights and their bundled license/notices. This is an **integrity check only**, not a warranty of model/voice/training rights.

## Third-party rights and redistribution

VoxWeaveTTS source code is MIT. Bundled Python and third-party runtimes have their own license obligations in the ZIP. Optional model weights belong to their upstream authors and are distributed as separate archives with rights notices. The SHA-256 catalog pins artifacts but does **not** grant a license.

All optional model rights are marked `review_required`. Do not infer blanket commercial clearance from an upstream code repository license. MakHam and FastThai training datasets declare CC BY 4.0 and must be attributed. **Supertonic 3 requires compliance with OpenRAIL-M use restrictions; Wayu is NonCommercial and not published as a v3 pack**. Check each `legal/rights.json`, license and attribution before use or redistribution.

See `docs/UNIVERSAL_VWMODEL_V3_TH.md` for the internal format, `docs/COMMERCIAL_LICENSE_POLICY_TH.md` for release policy, and `docs/V3_DEVELOPMENT_HANDOFF_2026-11-19_TH.md` for the development test record. This is not legal advice.
