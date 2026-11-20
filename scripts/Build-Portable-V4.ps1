# Windows Portable v4: v3 MakHam bootstrap remains installed; the Core additionally
# supports arbitrary opt-in Universal v4 external TTS workers and bundled wheels.
param([string]$Version = '0.12.0-dev0', [switch]$SkipZip, [string]$StageDirectory = '')
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$stage=Join-Path $root 'dist\VoxWeaveTTS'
if ($StageDirectory) {
  if (!$SkipZip) {throw 'Custom staging requires -SkipZip'}
  $stage=[IO.Path]::GetFullPath($StageDirectory)
}
# Reuse the already-qualified Windows/Python/MakHam staging recipe. Explicitly
# keep the previous v3 models installed and operational; no v2 fallback.
& (Join-Path $PSScriptRoot 'Build-Portable-V3.ps1') -Version $Version -SkipZip -StageDirectory $StageDirectory
if (!(Test-Path -LiteralPath (Join-Path $stage 'VoxWeaveTTS.exe'))) {
  throw 'Base Portable stage executable is missing'
}
# Build-Portable-V3 ends with a successful robocopy status (1..7) and
# PowerShell retains that code in LASTEXITCODE. It is not a build failure.
# Only v4 package-authoring examples ship with the new Portable.
$exampleSource=Join-Path $root 'examples'
$exampleTarget=Join-Path $stage 'examples'
if (Test-Path -LiteralPath $exampleTarget) {Remove-Item -LiteralPath $exampleTarget -Recurse -Force}
New-Item -ItemType Directory -Path $exampleTarget -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $exampleSource 'README_TH.md') -Destination $exampleTarget -Force
Get-ChildItem -LiteralPath $exampleSource -Directory | ForEach-Object {
  if (!$_.Name.StartsWith('v4-')) {throw ('Unsupported legacy example in v4: '+$_.Name)}
  Copy-Item -LiteralPath $_.FullName -Destination $exampleTarget -Recurse -Force
}
Get-ChildItem -LiteralPath $exampleTarget -Directory -Recurse -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $exampleTarget -Recurse -File -Filter '*.pyc' -ErrorAction SilentlyContinue | Remove-Item -Force
$required=@(
  'src\voxweavetts\universal_model_v4.py',
  'src\voxweavetts\engine_worker_gateway.py',
  'src\voxweavetts\engine_provider_catalog.py',
  'src\voxweavetts\package_install_v3.py',
  'runtime\python\python.exe',
  'runtime\tools\uv.exe',
  'docs\UNIVERSAL_VWMODEL_V4_TH.md',
  'examples\README_TH.md',
  'examples\v4-demo-tone\plugin\worker.py',
  'examples\v4-model-plugin\plugin\worker.py',
  'examples\v4-translation-plugin\plugin\worker.py',
  'web\index.html'
)
foreach ($name in $required) {
  if (!(Test-Path -LiteralPath (Join-Path $stage $name))) {
    throw ("Missing Universal v4 Portable component: "+$name)
  }
}
$py=Join-Path $stage 'runtime\python\python.exe'
$env:PYTHONPATH=Join-Path $stage 'src'
& $py -X utf8 -c 'from voxweavetts.universal_model_v4 import VERSION, PROTOCOL; assert VERSION==4 and PROTOCOL==1; from voxweavetts.engine_provider_catalog import all_providers; assert isinstance(all_providers(),dict)'
if ($LASTEXITCODE -ne 0) {throw 'V4 plugin-host import gate failed'}
if (!(Select-String -LiteralPath (Join-Path $stage 'web\index.html') -Pattern 'Universal .vwmodel v4/v3' -Quiet -SimpleMatch)) {
  throw 'One-click Universal v4 UI missing'
}
Write-Output ("V4_PORTABLE_STAGE="+$stage)
Write-Output "V4_PLUGIN_PROTOCOL=1"
Write-Output "V3_INSTALLED_MODELS_PRESERVED=True"
if (!$SkipZip) {
  $zip=Join-Path $root ("dist\VoxWeaveTTS-v{0}-portable.zip" -f $Version)
  if (Test-Path -LiteralPath $zip) {throw 'Portable v4 output already exists; refusing overwrite'}
  if (!(Get-Command tar.exe -ErrorAction SilentlyContinue)) {throw 'Windows tar.exe required for streaming v4 ZIP'}
  & tar.exe -a -c -f $zip -C (Join-Path $root 'dist') 'VoxWeaveTTS'
  if ($LASTEXITCODE -ne 0) {throw 'V4 Portable archive failed'}
  if ((Get-Item -LiteralPath $zip).Length -lt 1000000) {throw 'Invalid v4 ZIP size'}
  Write-Output ("V4_PORTABLE_ZIP="+$zip)
  Write-Output ("V4_PORTABLE_ZIP_SHA256="+(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash)
}
$global:LASTEXITCODE = 0
