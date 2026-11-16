# Install a trusted TTS provider in an isolated Python environment.
# Does not change VoxWeaveTTS's main .venv or run .vwmodel contents.
[CmdletBinding()]
param(
    [string]$Provider = "all",
    [switch]$TrustExecutableCode
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$main = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $main)) {
    $main = Join-Path $root 'runtime\python\python.exe'
}
if (-not (Test-Path $main)) {
    throw 'VoxWeaveTTS main Python runtime is not installed'
}
$env:PYTHONPATH = Join-Path $root 'src'
$env:UV_CACHE_DIR = Join-Path $root 'cache\uv'
$env:UV_LINK_MODE = 'copy'
$env:HF_HOME = Join-Path $root 'cache\huggingface'
$env:TEMP = Join-Path $root 'cache\temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

$known = @('wayu-nc','pythaitts','vachana','kokoro','sherpa')
$names = if ($Provider -eq 'all') { $known } else { @($Provider) }
foreach ($name in $names) {
    if ($TrustExecutableCode) {
        Write-Warning ("You are explicitly trusting executable Python code in extensions/engine-providers/{0}" -f $name)
        & $main -m voxweavetts.engine_provider_installer approve-install $name --trust-executable-code
    } else {
        & $main -m voxweavetts.engine_provider_installer install $name
    }
    if ($LASTEXITCODE -ne 0) {
        throw ("Failed installing provider {0}: code {1}" -f $name,$LASTEXITCODE)
    }
}
Write-Output 'Provider installation completed. Restart VoxWeaveTTS if an external provider was just approved.'
