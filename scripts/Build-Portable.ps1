# Official Windows Portable builder: Universal v4 plugins plus existing v3 models.
param([string]$Version = '0.12.0-dev0', [switch]$SkipZip, [string]$StageDirectory = '')
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Build-Portable-V4.ps1') -Version $Version -SkipZip:$SkipZip -StageDirectory $StageDirectory
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
