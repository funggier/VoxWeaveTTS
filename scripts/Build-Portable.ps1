# Official Windows Portable builder: v3-only runtime and model packages.
param([string]$Version = '0.11.0', [switch]$SkipZip, [string]$StageDirectory = '')
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Build-Portable-V3.ps1') -Version $Version -SkipZip:$SkipZip -StageDirectory $StageDirectory
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
