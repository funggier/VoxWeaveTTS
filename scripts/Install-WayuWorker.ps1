# Backwards-compatible wrapper for the generic isolated TTS provider installer.
[CmdletBinding()]
param([switch]$DownloadModel)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'Install-EngineProvider.ps1') -Provider 'wayu-nc'
if ($LASTEXITCODE -ne 0) { throw 'Wayu worker setup failed' }
if ($DownloadModel) {
    Write-Warning 'Wayu model weights are licensed CC BY-NC 4.0. Do not use them commercially.'
    $root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $worker=Join-Path $root 'runtime\engine-envs\wayu-nc\Scripts\python.exe'
    $model=Join-Path $root 'models\personal\wayu-paxa-tts-edge'
    & $worker -c "from huggingface_hub import snapshot_download; snapshot_download('wayu-ai/wayu-paxa-tts-edge', revision='8196688df56a8d08ccfa186505343adff412ab6b', allow_patterns=['config.json','model.pth','voices/*.pt','README.md'], local_dir=r'$model')"
    if ($LASTEXITCODE -ne 0) { throw 'Wayu NC model weights download failed' }
}
