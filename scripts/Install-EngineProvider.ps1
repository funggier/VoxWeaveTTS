# Install a trusted TTS provider in an isolated Python environment.
# Does not change VoxWeaveTTS's main .venv or run .vwmodel contents.
[CmdletBinding()]
param(
    [string]$Provider = "all",
    [switch]$TrustExecutableCode,
    [switch]$AcceptProviderTerms,
    [switch]$AcknowledgeNonCommercial
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
$known = @('wayu-nc','pythaitts','vachana','kokoro','sherpa')
$names = if ($Provider -eq 'all') { $known } else { @($Provider) }
foreach ($name in $names) {
    $held = $name -in @('wayu-nc','vachana','kokoro')
    if ($held -and $Provider -eq 'all') {
        Write-Warning ("Skipping {0}; select -Provider {0} explicitly to review and accept its own terms" -f $name)
        continue
    }
    if ($held -and -not $AcceptProviderTerms) {
        throw ("{0}: explicit -AcceptProviderTerms is required for optional local install; review docs/PROVIDER_RIGHTS_READINESS_TH.md" -f $name)
    }
    if ($name -eq 'wayu-nc' -and -not $AcknowledgeNonCommercial) {
        throw 'Wayu model weights are CC BY-NC 4.0. Explicit -AcknowledgeNonCommercial is required.'
    }
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    $accept = @()
    if ($held) { $accept += '--accept-provider-terms' }
    if ($name -eq 'wayu-nc') { $accept += '--acknowledge-noncommercial' }
    if ($TrustExecutableCode) {
        Write-Warning ("You are explicitly trusting executable Python code in extensions/engine-providers/{0}" -f $name)
        & $main -m voxweavetts.engine_provider_installer approve-install $name --trust-executable-code @accept
    } else {
        & $main -m voxweavetts.engine_provider_installer install $name @accept
    }
    if ($LASTEXITCODE -ne 0) {
        throw ("Failed installing provider {0}: code {1}" -f $name,$LASTEXITCODE)
    }
}
Write-Output 'Provider installation completed. Restart VoxWeaveTTS if an external provider was just approved.'
