# Official Windows Portable builder: Universal .vwmodel v4 ONLY.
param([string]$Version = '0.12.8', [switch]$SkipZip, [string]$StageDirectory = '', [switch]$IncludeUnreleasedQaMakHam)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Build-Portable-V4.ps1') -Version $Version -SkipZip:$SkipZip -StageDirectory $StageDirectory -IncludeUnreleasedQaMakHam:$IncludeUnreleasedQaMakHam
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
