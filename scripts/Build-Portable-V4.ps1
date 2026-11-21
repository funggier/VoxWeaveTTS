# Universal v4-only self-contained Windows Portable. No v3 installer, assets or runtime.
param(
  [string]$Version='0.12.4',
  [switch]$SkipZip,
  [string]$StageDirectory='',
  [switch]$IncludeUnreleasedQaMakHam
)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venv=Join-Path $root '.venv\Scripts\python.exe'
$site=Join-Path $root '.venv\Lib\site-packages'
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
if (!(Test-Path $venv) -or !(Test-Path $site) -or !(Test-Path $compiler)) {
  throw 'Python 3.11 dev venv or Windows C# compiler missing'
}
$pythonHome=(& $venv -c 'import sys; print(sys.base_prefix)').Trim()
if ($LASTEXITCODE -ne 0 -or !(Test-Path (Join-Path $pythonHome 'LICENSE.txt'))) {
  throw 'Portable Python runtime not found'
}
$stage=Join-Path $root 'dist\VoxWeaveTTS'
$distRoot=[IO.Path]::GetFullPath((Join-Path $root 'dist'))
if ($StageDirectory) {
  $stage=[IO.Path]::GetFullPath($StageDirectory)
  if (!$SkipZip -and (Split-Path $stage -Leaf) -ne 'VoxWeaveTTS') {
    throw 'ZIP staging directory must be named VoxWeaveTTS'
  }
}
if (!$stage.StartsWith(($distRoot.TrimEnd('\')+'\'),[StringComparison]::OrdinalIgnoreCase)) {
  throw 'Portable stage must be inside project dist/'
}
$zip=Join-Path $root ("dist\VoxWeaveTTS-v{0}-portable.zip" -f $Version)
$makArchive=Join-Path $root 'dist\ModelPackagesV4-QA\VoxWeaveTTS-makham-paradee-1.0.0-UNRELEASED-QA-format-v4.vwmodel'
if ($IncludeUnreleasedQaMakHam) {
  if (!$SkipZip) { throw 'UNRELEASED-QA MakHam cannot be included in a public ZIP' }
  if (!(Test-Path -LiteralPath $makArchive -PathType Leaf)) {
    throw 'QA MakHam v4 archive is missing'
  }
}
if (!$SkipZip -and (Test-Path -LiteralPath $zip -PathType Leaf)) {
  throw 'Release ZIP already exists; refusing to overwrite it'
}

function Copy-Tree([string]$source,[string]$destination,[string[]]$skip=@(),[string[]]$skipDirs=@()) {
  if (!(Test-Path -LiteralPath $source)) {throw "Required input missing: $source"}
  New-Item -ItemType Directory -Force -Path $destination | Out-Null
  $opts=@($source,$destination,'/E','/NFL','/NDL','/NJH','/NJS','/NP',
          '/XD','__pycache__','.git','.venv','tests','test','.pytest_cache')+$skipDirs+
          @('/XF','*.pyc','*.pyo')+$skip
  & robocopy @opts | Out-Null
  if ($LASTEXITCODE -ge 8) {throw "File copy failed: $source"}
}
if (Test-Path -LiteralPath $stage) {Remove-Item -LiteralPath $stage -Recurse -Force}
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Tree (Join-Path $root 'src') (Join-Path $stage 'src') @(
  'universal_model_packages.py','portable_runtime_v3.py','package_install_v3.py',
  'makham_package.py','engine_worker_host.py','engine_worker_legacy.py',
  'engine_worker_wayu.py','personal_wayu_engine.py','kokoro_engine.py',
  'sherpa_voice_engine.py','m2m_worker.py','m2m_smoke.py',
  'offline_wheelhouse.py','provider_signing.py'
)
Copy-Tree (Join-Path $root 'web') (Join-Path $stage 'web')
Copy-Tree (Join-Path $root 'extensions') (Join-Path $stage 'extensions') -skipDirs @('engine-providers')
Copy-Tree (Join-Path $root 'docs') (Join-Path $stage 'docs') @('*v3*','*V3*','*v2*','*V2*')
Copy-Tree (Join-Path $root 'examples') (Join-Path $stage 'examples')
# Preserve unmodified license texts for the actual embedded uv.exe binary.
Copy-Tree (Join-Path $root 'third_party_licenses') (Join-Path $stage 'third_party_licenses')
if (!(Test-Path (Join-Path $stage 'docs\UNIVERSAL_VWMODEL_V4_TH.md'))) {
  throw 'V4 package protocol documentation missing'
}
$oldModels = Join-Path $stage 'models\universal\v3'
if (Test-Path -LiteralPath $oldModels) {throw 'v3 assets leaked into v4 Portable'}
foreach ($name in @('LICENSE','README_TH.md','README.md')) {
  Copy-Item -LiteralPath (Join-Path $root $name) -Destination (Join-Path $stage $name) -Force
}
$runtime=Join-Path $stage 'runtime\python'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
foreach ($name in @('python.exe','pythonw.exe','python3.dll','python311.dll',
                     'vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt')) {
  $from=Join-Path $pythonHome $name
  if (Test-Path $from) {Copy-Item $from (Join-Path $runtime $name) -Force}
}
Copy-Tree (Join-Path $pythonHome 'Lib') (Join-Path $runtime 'Lib') -skipDirs @('site-packages')
Copy-Tree (Join-Path $pythonHome 'DLLs') (Join-Path $runtime 'DLLs')
Copy-Tree (Join-Path $pythonHome 'tcl') (Join-Path $runtime 'tcl')
# The public Core contains ONLY its required v4 protocol / YouTube stream
# dependencies. ML inference stays in user-selected external .vwmodel v4.
$coreSite=Join-Path $runtime 'Lib\site-packages'
New-Item -ItemType Directory -Force -Path $coreSite | Out-Null
foreach ($pattern in @('packaging','packaging-*.dist-info',
                      'grpc','grpcio-*.dist-info',
                      'google','protobuf-*.dist-info',
                      'typing_extensions.py','typing_extensions-*.dist-info')) {
  $hits=@(Get-ChildItem -LiteralPath $site -Filter $pattern -Force)
  if ($hits.Count -ne 1) {throw ('Core dependency not uniquely present: '+$pattern)}
  $src=$hits[0].FullName
  $dest=Join-Path $coreSite $hits[0].Name
  if ($hits[0].PSIsContainer) { Copy-Tree $src $dest }
  else { Copy-Item -LiteralPath $src -Destination $dest -Force }
}
& (Join-Path $runtime 'python.exe') -X utf8 -c 'import packaging,grpc,typing_extensions;from google import protobuf;assert packaging.__version__ and grpc.__version__ and protobuf.__version__'
if ($LASTEXITCODE -eq 0) { Write-Output 'CORE_DEPENDENCIES_READY' }
if ($LASTEXITCODE -ne 0) {throw 'Minimal v4 Core dependencies are incomplete'}
foreach ($dir in @('presets','models\packages','models\recovery-packages',
                   'cache\temp','cache\torch','cache\huggingface',
                   'voices','output','logs','data\settings','data\reading',
                   'data\filters','data\dictionaries','data\presets',
                   'data\profiles','models\ai','config','runtime\tools')) {
  New-Item -ItemType Directory -Force -Path (Join-Path $stage $dir) | Out-Null
}
$uvPath=(Get-Command uv -ErrorAction Stop).Source
Copy-Item $uvPath (Join-Path $stage 'runtime\tools\uv.exe') -Force
$env:PYTHONPATH=Join-Path $stage 'src'
$env:PYTHONNOUSERSITE='1'
$python=Join-Path $stage 'runtime\python\python.exe'
& $python -X utf8 -c 'from voxweavetts.universal_model_v4 import VERSION; assert VERSION==4; from voxweavetts.engine_provider_catalog import all_providers; assert isinstance(all_providers(),dict)'
if ($LASTEXITCODE -ne 0) {throw 'V4-only Core import validation failed'}
# Only a private, explicitly opted-in QA build may bundle the reviewed-pending
# MakHam runtime. The PUBLIC v4 Core is deliberately model-free by default.
if ($IncludeUnreleasedQaMakHam) {
  & $python -X utf8 (Join-Path $root 'scripts\bootstrap_v4_portable.py') --stage $stage --package $makArchive
  if ($LASTEXITCODE -ne 0) {throw 'Failed to install offline v4 QA default voice'}
  Copy-Item -LiteralPath $makArchive -Destination (Join-Path $stage 'models\recovery-packages\VoxWeaveTTS-MakHam-v4.vwmodel') -Force
  & $python -X utf8 (Join-Path $root 'scripts\bootstrap_v4_portable.py') --stage $stage --verify-only
  if ($LASTEXITCODE -ne 0) {throw 'v4 QA MakHam readiness failed'}
} else {
  & $python -X utf8 -c 'import sys;from pathlib import Path;from voxweavetts.universal_model_v4 import installed_packages;root=Path(sys.argv[1]);assert not installed_packages(root)' $stage
  if ($LASTEXITCODE -ne 0 -or @(Get-ChildItem $stage -Recurse -File -Filter '*.vwmodel').Count -ne 0) {
    throw 'A model archive entered the public Core stage'
  }
  Write-Output 'PUBLIC_V4_CORE_NO_MODEL_ASSETS_PASS'
}
$notice=@(
  "VoxWeaveTTS v$Version - third-party notices for the v4 Core",
  "VoxWeaveTTS source: MIT - see LICENSE",
  "Embedded CPython: Python Software Foundation License - see runtime/python/LICENSE.txt",
  "uv 0.12.9 (astral-sh/uv): MIT OR Apache-2.0 - see third_party_licenses/uv/LICENSE-MIT, LICENSE-APACHE and SOURCE.json",
  "grpcio 1.85.1: Apache-2.0 - see runtime/python/Lib/site-packages/grpcio-1.85.1.dist-info/licenses/LICENSE",
  "protobuf 7.36.2: BSD-3-Clause - see runtime/python/Lib/site-packages/protobuf-7.36.2.dist-info/LICENSE",
  "packaging 26.3: Apache-2.0 OR BSD-2-Clause - see runtime/python/Lib/site-packages/packaging-26.3.dist-info/licenses/",
  "typing_extensions 4.16.0: PSF-2.0 - see runtime/python/Lib/site-packages/typing_extensions-4.16.0.dist-info/licenses/",
  "The v4 Core includes NO model weights, training datasets, model runtime wheels, or QA model assets.",
  "Users obtain v4 .vwmodel packages separately; the Core validates and installs them offline.",
  "Model author/license claims are not assurances of independent redistribution rights.",
  "Source and attribution references: docs/V4_RIGHTS_REVIEW_TH.md"
)
$notice | Set-Content -LiteralPath (Join-Path $stage 'THIRD_PARTY_NOTICES.txt') -Encoding UTF8
$exe=Join-Path $stage 'VoxWeaveTTS.exe'
& $compiler /nologo /target:winexe /platform:x64 ("/out:"+$exe) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll (Join-Path $root 'scripts\VoxWeaveTTS.Launcher.cs')
if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $exe)) {
  throw 'Windows launcher build failed'
}
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'scripts') | Out-Null
Copy-Item (Join-Path $root 'Stop-VoxWeaveTTS.cmd') (Join-Path $stage 'Stop-VoxWeaveTTS.cmd') -Force
Copy-Item (Join-Path $root 'scripts\Stop-VoxWeaveTTS.ps1') (Join-Path $stage 'scripts\Stop-VoxWeaveTTS.ps1') -Force
Copy-Item (Join-Path $root 'scripts\Check-Portable.ps1') (Join-Path $stage 'scripts\Check-Portable.ps1') -Force
@'
@echo off
call "%~dp0Stop-VoxWeaveTTS.cmd" %*
exit /b %ERRORLEVEL%
'@ | Set-Content -LiteralPath (Join-Path $stage 'Stop-Console.cmd') -Encoding Ascii
@'
@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
set "PYTHONNOUSERSITE=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "HF_HOME=%CD%\cache\huggingface"
set "TORCH_HOME=%CD%\cache\torch"
set "XDG_CACHE_HOME=%CD%\cache"
set "TEMP=%CD%\cache\temp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"
"%CD%\runtime\python\python.exe" -m voxweavetts --port 8765
if errorlevel 1 pause
endlocal
'@ | Set-Content -LiteralPath (Join-Path $stage 'Start-Console.cmd') -Encoding Ascii
# The user requested v4-only examples in the distribution.
$examples=@(Get-ChildItem (Join-Path $stage 'examples') -Directory)
if (@($examples | Where-Object { !$_.Name.StartsWith('v4-') }).Count -ne 0) {
  throw 'Non-v4 package authoring examples were included'
}
if ((Get-ChildItem $stage -Recurse -File -Filter '*.vwmodel' | Where-Object {
      $_.FullName -match 'format-v[123]|ModelPackagesV3'
    }).Count -ne 0) {throw 'Older model archives detected in v4 build'}
if (!(Select-String -LiteralPath (Join-Path $stage 'web\index.html') -Pattern 'Universal .vwmodel v4 (' -SimpleMatch -Quiet)) {
  throw 'V4-only package UI missing'
}
Write-Output ("V4_ONLY_PORTABLE_STAGE="+$stage)
if ($IncludeUnreleasedQaMakHam) { Write-Output ("V4_QA_DEFAULT_PACKAGE="+$makArchive) }
else { Write-Output "V4_PUBLIC_CORE_MODEL_PACKAGES=0" }
Write-Output "V4_PROTOCOL=1"
Write-Output "V4_LEGACY_PACKAGE_SUPPORT=False"
Write-Output ("V4_UNRELEASED_QA_MAKHAM_INCLUDED="+$IncludeUnreleasedQaMakHam.ToString())
if (!$SkipZip) {
  if (Test-Path -LiteralPath $zip) {
    throw 'V4 ZIP output exists; refusing to overwrite'
  }
  & tar.exe -a -c -f $zip -C (Split-Path $stage -Parent) (Split-Path $stage -Leaf)
  if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $zip)) {
    throw 'V4 Portable ZIP build failed'
  }
  Write-Output ("V4_PORTABLE_ZIP="+$zip)
  Write-Output ("V4_PORTABLE_ZIP_SHA256="+(Get-FileHash $zip -Algorithm SHA256).Hash)
}
$global:LASTEXITCODE=0
