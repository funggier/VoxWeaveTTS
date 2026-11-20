# VoxWeaveTTS — Current architecture (Universal v4 only)

## Platform

VoxWeaveTTS is a Windows Portable app. Its Core owns the HTTP/Web UI, Live input adapters, text normalization, filtering, translation routing, speech queue, playback events, and subtitle/OBS overlay. Model inference is deliberately **out-of-process**.

### Model format

All installable models are **Universal .vwmodel v4**. A package includes `manifest.json` and its own `plugin/worker.py` or Native `plugin/worker.exe`, model assets, rights declarations and offline dependencies. The user explicitly chooses and installs the package. The Core never imports a model-specific adapter or accepts a v1/v2/v3 archive.

The Core validates the ZIP manifest and hashes, installs bundled Python 3.11 Wheels using offline uv in an isolated local runtime, or runs a self-contained native worker. Paths are recalculated from the application's current root for relocatable operation. A v4 archive containing executable code is a user trust decision, **not a sandbox**.

### IPC boundaries

TTS workers: JSON Lines over stdin/stdout, `synthesize` request, PCM16 Mono Base64 response. Each worker is a separate process and lifecycle is managed by the gateway. Audio then flows through DSP, shared queue, timeline and overlay.

Translation workers: JSON Lines, `translate` request and text response. The current M2M100 package uses this protocol. Ollama-based translation is a separate user-configured local service and not an installable TTS model.

### Source code

- `src/voxweavetts/universal_model_v4.py`: versioned archive validation, install/uninstall and isolated runtime layout
- `src/voxweavetts/package_install_v4.py`: local picker token and single-click consent
- `src/voxweavetts/engine_provider_catalog.py`: dynamic v4 TTS engine discovery
- `src/voxweavetts/engine_worker_gateway.py`: child-process IPC and memory management
- `src/voxweavetts/speech.py`: generic TTS registry, chunking, DSP, timing
- `src/voxweavetts/m2m_runtime.py`: v4 translation worker lifecycle
- `src/voxweavetts/server.py`: HTTP API and Web UI
- `scripts/Build-Portable-V4.ps1`: v4-only Windows Portable build

[Universal v4 package protocol](UNIVERSAL_VWMODEL_V4_TH.md) · [QA model inventory](V4_ALL_MODEL_QA_TH.md) · [API](API.md).
