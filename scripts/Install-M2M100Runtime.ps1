# One-shot installer for the isolated optional M2M100 AI worker.
# No model weights are downloaded; only pinned Python dependencies are installed.
param()
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python=Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path $python)) {$python=Join-Path $root 'runtime\python\python.exe'}
if (!(Test-Path $python)) {throw 'VoxWeaveTTS Python runtime not found'}
$env:PYTHONPATH=Join-Path $root 'src'
$env:PYTHONUTF8='1'
& $python -m voxweavetts.m2m_runtime install
if ($LASTEXITCODE -ne 0) {throw 'M2M100 runtime installation failed'}
Write-Output 'M2M100 isolated runtime is ready'
