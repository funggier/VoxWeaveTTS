# Read-only portable runtime / model diagnosis. Never installs or downloads.
[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$VerifyWheelhouse,
    [switch]$Strict
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root 'runtime\python\python.exe'
if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    $python=Join-Path $root '.venv\Scripts\python.exe'
}
if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Portable Python runtime is missing; restore the complete ZIP'
}
$env:PYTHONPATH=Join-Path $root 'src'
$env:PYTHONNOUSERSITE='1'
$argsForPython=@('-m','voxweavetts.portable_doctor','--root',$root)
if ($Json) {$argsForPython+='--json'}
if ($VerifyWheelhouse) {$argsForPython+='--verify-wheelhouse'}
if ($Strict) {$argsForPython+='--strict'}
& $python @argsForPython
exit $LASTEXITCODE
