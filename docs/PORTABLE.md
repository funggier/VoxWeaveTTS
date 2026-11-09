# Windows portable distribution — target, NOT shipped

Goal: `VoxWeaveTTS-vX.Y.Z-portable.zip` with a bundled self-contained runtime, launch executable, web UI, config, user data, voice profiles, and optional separately licensed model packs.

## Folder layout

```text
VoxWeaveTTS/
  VoxWeaveTTS.exe             # future build
  StartServer.exe             # future build
  runtime/                    # bundled native/python dependencies
  src/                        # developer checkout only
  web/
  data/                       # dictionaries, filters, presets, profiles, settings, db
  voices/                     # private voice reference recordings
  models/                     # third-party model packs with own licensing
  cache/                      # audio and model caches
  output/
  logs/
```

All app-generated paths resolve from the executable location, never from a hard-coded drive letter. Avoid silently routing Torch/HF/TEMP artifacts to the Windows profile: configure process-specific cache environment variables before model imports. Respect GPU driver prerequisites, verify Windows compatibility and clean-machine launch. The selected model must legally allow redistribution before inclusion in a full-archive build.

The present development launcher `Start-Dev.cmd` requires a preinstalled Python because the portable build pipeline has not yet been implemented. Do not represent this checkout as a finished portable binary.

## Privacy and upgrades

Never publish `voices/`, `models/`, `data/`, `cache/`, tokens or local settings. Bundle only sample configuration under `config/`. Preserve user data on application upgrade with backup-before-migration and forward-compatible schema.
