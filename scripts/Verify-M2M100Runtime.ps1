# Opt-in M2M100 CPU inference smoke; never downloads model/dependencies.
[CmdletBinding()]
param(
    [switch]$Json,
    [ValidateRange(15,180)]
    [int]$TimeoutSeconds=120
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root 'runtime\python\python.exe'
if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    $python=Join-Path $root '.venv\Scripts\python.exe'
}
if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Portable Python runtime is missing'
}
$env:PYTHONPATH=Join-Path $root 'src'
$env:PYTHONNOUSERSITE='1'
$env:PYTHONIOENCODING='utf-8'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$argvForPython=@('-m','voxweavetts.m2m_smoke','--timeout',[string]$TimeoutSeconds)
if ($Json) {$argvForPython+='--json'}
& $python @argvForPython
exit $LASTEXITCODE
