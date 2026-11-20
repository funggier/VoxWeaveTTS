# VoxWeaveTTS v4 — Portable for Windows

The current source and new Portable distribution accept **only Universal .vwmodel v4**.

After obtaining a verified Windows Portable build, unzip it into any directory, then run `VoxWeaveTTS.exe` (or `Start-Console.cmd`). Local settings, cache, installed model packages and isolated Python environments remain in the application folder and support relocation.

Use the Model Packages screen to choose one .vwmodel v4 file and install it. Every Python dependency must be inside the package; the installer uses local uv offline. The user does not need to run pip or choose a Python version.

A new Portable QA build includes MakHam v4 as the default voice and a v4 recovery archive. **It does not ship optional third-party model archives**; these are still under redistribution-rights review.

For development:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Portable.ps1 -Version 0.12.0-dev0 -SkipZip -StageDirectory dist\VoxWeaveTTS-v4-validation
.\dist\VoxWeaveTTS-v4-validation\runtime\python\python.exe -X utf8 scripts\verify_v4_portable_stage.py --stage dist\VoxWeaveTTS-v4-validation
```

The builder requires the local MakHam v4 QA archive in `dist/ModelPackagesV4-QA`. This is a **development QA build, not permission to publish model weights**.

[Package protocol](UNIVERSAL_VWMODEL_V4_TH.md) · [Model QA](V4_ALL_MODEL_QA_TH.md) · [Portable diagnostics](PORTABLE_DIAGNOSTICS_TH.md).
