# VoxWeaveTTS

**Windows Portable TTS Studio v0.12.7 — Universal .vwmodel v4 only**

**Parallel Ollama translation (v0.12.7).** Live modes with prepare-ahead can share up to 64 in-flight translation slots, with a configurable gathering threshold and a short tail flush. The original order governs audio rendering and playback.

**Batch model installation (v0.12.6).** In Settings, select multiple offline .vwmodel v4 packages in the Windows chooser with Ctrl or Shift. The app installs each file and reports individual failures.

**Shared Rules (v0.12.5).** Edit and import or export the two AI stages in separate JSON fields. The in-app save writes both stages to the existing settings file.

**Language-route save latency fix (v0.12.5):** Save now uses one integrity-checked installed-v4 manifest snapshot for the whole set of language routes, instead of repeatedly enumerating and hashing model assets for every language. Voice/engine/declared-language validation, optimistic revision checks and atomic file replacement remain enforced. Preset refresh reads each JSON file once and reuses engine descriptors only within a single refresh; subsequent requests recheck installed packages. Speech rendering reuses descriptors within one job and mixed-language spans rather than repeatedly scanning the same v4 workers. No cross-request model-integrity cache or background worker restarts are introduced. The Save controls show an immediate in-progress status. Local benchmark: two language routes, 20 installed-model scans / ~105 ms before, one scan / ~4 ms after; values vary across systems.

**New in v0.12.4 — expanded Live queue controls:** All six Live modes independently support **1–100 advance text/AI preparation slots** (default 3) and **1–20 ready/rendering WAV slots** (default 2), with no combined 10-slot cap. The bounded shared registry allows up to 768 jobs and a 512 MB global synthesized-WAV cache; these are upper bounds, not guaranteed simultaneous rendering or playback throughput. Per-source speech-job timeout is configurable from **1–60 minutes** (default 4); intentional wait for a ready WAV render slot does not consume processing time. The renamed **Continue reading when errors occur** option skips failed/timed-out translation or synthesis jobs and continues FIFO; browser autoplay permission denials still need user intervention. The previous saved per-mode settings migrate without data loss.

**New in v0.12.4 — optional continuation on blocked audio:** A new per-Live-mode, default-off **บังคับเล่นเสียงต่ออัตโนมัติ** checkbox opts in to skipping every Browser autoplay-blocked WAV (including NotAllowedError / SecurityError) and attempting the next queued message in FIFO order, with no consecutive-skip cap. This does **not** grant or override browser audio permission; if the browser denies all attempts, all incoming messages may be skipped without audible playback, intentionally. The UI tracks Browser-blocked skips. The setting is separate from general speech/translation error continuation and migrates from existing per-mode preferences with its default off.

**Original v0.12.3 opt-in Live prefetch pipeline (historical limits; expanded in v0.12.4 above):** The six Live modes now have independently persisted, configurable preparation/translation queue depth (1–8, default 3) and ready-audio queue depth (1–8, default 2), with their combined limit capped at 10, not including the active WAV or incoming raw-chat queue. AI preparation and WAV synthesis can overlap previous playback while preserving FIFO; opt-in random chat pruning applies to the unprocessed raw chat only. See [Thai release notes](docs/RELEASE_NOTES_v0.12.3_TH.md).

**[Public v0.12.7](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.7) is a full Windows Portable Core ZIP, without model weights.** It fixes the v0.12.1 installer rejecting the original GPL/LGPL source archives shipped inside Kokoro and Wayu V4 packages. Download the [seven separately licensed offline V4 model packs](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4) without repackaging or redownloading them. Vachana / `vachanatts` stays local-only pending code rights verification.

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

The **published Core-only Portable** contains no default voice. Install the optional first-party Windows SAPI Desktop v4 package for real English speech using an existing desktop voice in Windows (not a machine-learning model, not Thai voice cloning), or install another trusted, license-compatible v4 package. A separate *demo tone* package exercises the protocol but does **not** synthesize speech.

## Build and package examples

The [v4 examples](examples/README_TH.md) cover Python plugin workers (with or without new offline wheels), native EXE workers, TTS model workers and translation workers. No legacy package examples remain in the examples directory.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\build_vwmodel_v4.py --source examples\v4-demo-tone --spec examples\v4-demo-tone\spec.json --output cache\demo-tone-v4.vwmodel
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Portable.ps1 -Version 0.12.7 -StageDirectory dist\release-v0.12.7\VoxWeaveTTS
```

Public Core builds require **no QA archives** and never ship models. An isolated **private QA-only** stage may opt into MakHam with `-SkipZip -IncludeUnreleasedQaMakHam`; the builder blocks ZIP publishing of that option. See [v0.12.7 release notes](docs/RELEASE_NOTES_v0.12.7_TH.md).

## Eight-model v4 QA and redistribution rights

All **seven TTS engines** (MakHam, FastThaiG2P, Melo Chinese, Supertonic 3, Kokoro, Vachana, Wayu NC) plus **M2M100 translation** have passed local offline installation and real audio or translation tests as v4 packages.

**Seven independent V4 model packs are publicly available** in the [model-packs Release](https://github.com/funggier/VoxWeaveTTS/releases/tag/v0.12.1-modelpacks-v4); they retain upstream licenses, including Wayu's noncommercial CC BY-NC 4.0 and the GPL/LGPL source obligations of selected runtime components. The eighth, **Vachana / `vachanatts`**, remains local-only. Older private QA archives remain under `dist/ModelPackagesV4-QA` and are not Release assets.

Prior public releases remain in [GitHub Releases](https://github.com/funggier/VoxWeaveTTS/releases) and Git history; this development branch and its new Portable build accept **only v4**.

Documentation: [v4 wheel license notice QA](docs/V4_DEPENDENCY_NOTICE_QA_2026-11-20_TH.md) · [v4-only QA handoff](docs/V4_ONLY_QA_HANDOFF_2026-11-20_TH.md) · [v4 protocol](docs/UNIVERSAL_VWMODEL_V4_TH.md) · [model QA report](docs/V4_ALL_MODEL_QA_TH.md) · [API](docs/API.md) · [translation](docs/AI_PROCESSING_TRANSLATION_TH.md) · [rights policy](docs/COMMERCIAL_LICENSE_POLICY_TH.md).


**Repeated-text rules (included in v0.12.4):** The shared Rule system and browser Quick Add support match_mode repeat_run (a literal character/emoji unit repeated consecutively) and phrase_run (an exact word or phrase repeated with whitespace between copies), with min_repeats from 2 to 1000. Three, five and seven-repeat thresholds may coexist, with the highest eligible minimum winning while matching the full run. phrase_run replacements with unspecified spoken collapse the phrase to one spoken copy; subtitles retain the original repeated text. Existing five_run, literal, skip, silence, sources, and per-stage processing remain compatible; no arbitrary regular expression evaluation.

**Standard emoji and YouTube built-in emotes (included in v0.12.4):** Per-Live-mode optional dictionaries support standard Unicode emoji from YouTube/Discord, YouTube's platform-wide :face-blue-smiling: and :yt: emotes, and Discord custom emoji markers <a:name:id> or <:name:id> matching via :name:. The YouTube Browser adapter retains image alt text and canonicalizes lowercase bare emote names to :name: while preserving case-sensitive legacy emote names, Unicode graphemes, and the original chat history. Unicode mappings match equivalent variation-selector representations; neutral emoji mappings can cover unlisted skin tones with exact per-tone overrides. This is dictionary-driven, not automatic translation of all emoji names. Unmapped emojis are preserved. Emoji image attachments and stickers are not downloaded or parsed; offline configuration stays at 64 mappings per mode.

**TikTok LIVE native emoji names (included in v0.12.4):** TikFinity's local WebSocket comments and the explicitly paired TikTok Extension now support opt-in per-source mappings for both standard Unicode emoji and TikTok bracketed emote identifiers such as [smile], [laughwithtears] and [cry]. In the emoji editor, [smile] = smile or :smile: = smile map an incoming [smile] token; an exact bracket mapping takes priority if both are configured. The Extension maps lowercase IMG alt/accessibility labels inside a comment body to [name], retaining literal bracketed tokens, uppercase legacy names and Unicode graphemes. The local TikFinity integration uses the actual inbound comment text; it does not infer missing emotes. TikTok LIVE rendering of proprietary shortcodes varies by client/feed. Stickers, gifts and sender badges are not treated as comment text. Stored raw messages remain unchanged and the shared literal, repeat_run and phrase_run rules can be applied downstream.
