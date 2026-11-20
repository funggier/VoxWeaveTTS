# Universal v4-only QA checksum generator. Public distribution remains rights-gated.
param(
  [string]$Version='0.12.1-dev0',
  [switch]$QA
)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python=Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path $python)) {throw 'Development Python is not available'}
$packages=Join-Path $root 'dist\ModelPackagesV4-QA'
if (!$QA) {
  & $python -X utf8 (Join-Path $root 'scripts\verify_v4_model_inventory.py') --packages $packages --require-cleared
  throw 'Public Release BLOCKED: v4 model/Dependency rights review is pending. Use -QA for private checksums only.'
}
& $python -X utf8 (Join-Path $root 'scripts\verify_v4_model_inventory.py') --packages $packages --deep
if ($LASTEXITCODE -ne 0) {throw 'v4 QA model integrity gate failed'}
$files=@(Get-ChildItem -LiteralPath $packages -File -Filter '*UNRELEASED-QA-format-v4.vwmodel' | Sort-Object Name)
if ($files.Count -ne 8) {throw ('Expected eight v4 QA archives, found '+$files.Count)}
$lines=@(
  '# UNRELEASED QA ONLY - NOT FOR PUBLIC DISTRIBUTION',
  '# v4 model weights and runtime wheel licensing not yet cleared'
)
foreach($file in $files) {
  $hash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  $lines+=("$hash *"+$file.Name)
}
$output=Join-Path $packages 'SHA256SUMS-v4-QA.txt'
$lines | Set-Content -LiteralPath $output -Encoding UTF8
Write-Output ('V4_QA_CHECKSUMS='+$output)
Write-Output 'PUBLIC_RELEASE_ALLOWED=False'
$global:LASTEXITCODE=0
