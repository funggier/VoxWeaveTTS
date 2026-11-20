# VoxWeaveTTS

**Windows Portable TTS Studio v0.12.0 — Universal .vwmodel v4 only**

**Public v0.12.0 is Core-only.** Its ZIP intentionally includes **no TTS or translation weights, no bundled model package, and no model-specific inference runtime.** Install a separately obtained, license-compatible `.vwmodel v4` package offline before attempting real text-to-speech. The eight migration QA packs are withheld pending redistribution review.

VoxWeaveTTS is a local-first, Thai-focused TTS application with narration, live chat, per-mode voice settings, translation, speech queues, APIs, and subtitle/OBS synchronization. Its model engines and offline dependencies live in separate, self-contained packages.

## Model packages

**Install → Choose a .vwmodel file → Ready.** Choosing and installing the file is the user's acceptance of its declared terms and executable plugin code. No additional license modal, online license server, or network dependency resolver is required.

- **Only Universal .vwmodel v4 is accepted.** There are no legacy v1/v2/v3 installers or built-in model-specific adapters in the current Core.
- Each package contains its own Worker Protocol implementation, model data, configuration, declared rights, and (if required) all offline Python wheels.
- Python 3.11 plugins run with isolated dependencies; native EXE plugins bring their own runtime.
- Models and environments are relocatable, with local settings/cache/voice presets.
- The Core verifies archive paths and file hashes and rejects unsafe Wheel startup hooks. It does not certify the author or sandbox third-party code.
- TTS and translation packages communicate using a stable, versioned JSON Lines protocol; Core manages playback queues and voice/subtitle events.

**Security:** A v4 plugin runs executable code with the user's Windows permissions. Installing it is a trust decision, not a guarantee of safety or permission to redistribute it.

## Studio features

Narration/document reading; Discord, YouTube LIVE and TikTok LIVE chat integrations; configurable pronunciation and filtering rules; per-language model routing; translation; voice controls; shared speech queue; subtitle/OBS overlay; local API.

The **published Core-only Portable** contains no default voice. Once the user installs a separately obtained compatible v4 engine, TTS and translation become available. A separate optional original *demo tone* package exercises the plugin system but does **not** synthesize speech.

## Build and package examples

The [v4 examples](examples/README_TH.md) cover Python plugin workers (with or without new offline wheels), native EXE workers, TTS model workers and translation workers. No legacy package examples remain in the examples directory.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\build_vwmodel_v4.py --source examples\v4-demo-tone --spec examples\v4-demo-tone\spec.json --output cache\demo-tone-v4.vwmodel
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Portable.ps1 -Version 0.12.0 -StageDirectory dist\release-v0.12.0\VoxWeaveTTS
```

Public Core builds require **no QA archives** and never ship models. An isolated **private QA-only** stage may opt into MakHam with `-SkipZip -IncludeUnreleasedQaMakHam`; the builder blocks ZIP publishing of that option. See [v0.12.0 release notes](docs/RELEASE_NOTES_v0.12.0_TH.md).

## Eight-model v4 QA and redistribution rights

All **seven TTS engines** (MakHam, FastThaiG2P, Melo Chinese, Supertonic 3, Kokoro, Vachana, Wayu NC) plus **M2M100 translation** have passed local offline installation and real audio or translation tests as v4 packages.

The eight archives under `dist/ModelPackagesV4-QA` are **not approved for public distribution**. Third-party model/Dependency rights remain under review. Wayu weights remain noncommercial (CC BY-NC 4.0); other models have their own distinct conditions. A user's installation click does not grant a developer redistribution rights.

Prior public releases remain in [GitHub Releases](https://github.com/funggier/VoxWeaveTTS/releases) and Git history; this development branch and its new Portable build accept **only v4**.

Documentation: [v4-only QA handoff](docs/V4_ONLY_QA_HANDOFF_2026-11-20_TH.md) · [v4 protocol](docs/UNIVERSAL_VWMODEL_V4_TH.md) · [model QA report](docs/V4_ALL_MODEL_QA_TH.md) · [API](docs/API.md) · [translation](docs/AI_PROCESSING_TRANSLATION_TH.md) · [rights policy](docs/COMMERCIAL_LICENSE_POLICY_TH.md).
