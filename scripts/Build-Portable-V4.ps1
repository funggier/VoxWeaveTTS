# Universal v4-only self-contained Windows Portable. No v3 installer, assets or runtime.
param(
  [string]$Version='0.12.0-dev0',
  [switch]$SkipZip,
  [string]$StageDirectory=''
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
  if (!$SkipZip) {throw 'Custom staging requires -SkipZip'}
  $stage=[IO.Path]::GetFullPath($StageDirectory)
}
if (!$stage.StartsWith(($distRoot.TrimEnd('\')+'\'),[StringComparison]::OrdinalIgnoreCase)) {
  throw 'Portable stage must be inside project dist/'
}
$zip=Join-Path $root ("dist\VoxWeaveTTS-v{0}-portable.zip" -f $Version)
$makArchive=Join-Path $root 'dist\ModelPackagesV4-QA\VoxWeaveTTS-makham-paradee-1.0.0-UNRELEASED-QA-format-v4.vwmodel'
if (!(Test-Path -LiteralPath $makArchive -PathType Leaf)) {
  throw 'MakHam v4 model package for offline bootstrap is missing; prepare v4 QA assets first'
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
Copy-Tree (Join-Path $pythonHome 'Lib') (Join-Path $runtime 'Lib')
Copy-Tree (Join-Path $pythonHome 'DLLs') (Join-Path $runtime 'DLLs')
Copy-Tree (Join-Path $pythonHome 'tcl') (Join-Path $runtime 'tcl')
# The Core has no built-in TTS weights, Torch, Transformers or model-specific
# runtime dependencies. Those are delivered by individual v4 .vwmodel files.
Copy-Tree $site (Join-Path $runtime 'Lib\site-packages') @('*.onnx','*.npy','*.pt','*.pth','*.wav','*.mp3','*.flac') @(
  'torch','torchgen','functorch','transformers','tokenizers','safetensors',
  'sentencepiece','sympy','networkx',
  'torch-*.dist-info','transformers-*.dist-info','tokenizers-*.dist-info',
  'safetensors-*.dist-info','sentencepiece-*.dist-info',
  'sympy-*.dist-info','networkx-*.dist-info',
  # Model-specific inference dependencies belong to .vwmodel v4 isolated
  # environments, never to the Portable Core Python site-packages.
  'pythaitts','pythaitts-*.dist-info',
  'onnxruntime','onnxruntime-*.dist-info',
  'kokoro_onnx','kokoro_onnx-*.dist-info',
  'sherpa_onnx','sherpa_onnx*.dist-info',
  'misaki','misaki-*.dist-info',
  'unidic_lite','unidic_lite-*.dist-info',
  'espeakng_loader','espeakng_loader-*.dist-info',
  'phonemizer','phonemizer-*.dist-info','phonemizer_fork-*.dist-info',
  'fugashi','fugashi.libs','fugashi-*.dist-info',
  'jaconv','jaconv-*.dist-info',
  'mojimoji','mojimoji-*.dist-info',
  'numpy','numpy.libs','numpy-*.dist-info',
  'scipy','scipy.libs','scipy-*.dist-info',
  'soundfile','soundfile-*.dist-info',
  'librosa','librosa-*.dist-info'
)
$coreSite=Join-Path $runtime 'Lib\site-packages'
foreach ($forbidden in @('pythaitts','onnxruntime','kokoro_onnx',
                         'sherpa_onnx','misaki','numpy','scipy')) {
  if (Test-Path -LiteralPath (Join-Path $coreSite $forbidden)) {
    throw ('Model-specific dependency leaked into v4 Core: '+$forbidden)
  }
}
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
# A new Portable must be usable immediately, with only a v4 MakHam model.
& $python -X utf8 (Join-Path $root 'scripts\bootstrap_v4_portable.py') --stage $stage --package $makArchive
if ($LASTEXITCODE -ne 0) {throw 'Failed to install offline v4 default voice'}
Copy-Item -LiteralPath $makArchive -Destination (Join-Path $stage 'models\recovery-packages\VoxWeaveTTS-MakHam-v4.vwmodel') -Force
& $python -X utf8 (Join-Path $root 'scripts\bootstrap_v4_portable.py') --stage $stage --verify-only
if ($LASTEXITCODE -ne 0) {throw 'Universal v4-only Portable readiness failed'}
$notice=@(
  "VoxWeaveTTS v$Version third-party notices (QA, redistribution review pending)",
  "VoxWeaveTTS Core: MIT, see LICENSE",
  "Embedded Python 3.11: PSF License, see runtime/python/LICENSE.txt",
  "Bundled uv and other Python dependencies: see their respective license files",
  "MakHam Paradee: model licensed as declared in its v4 manifest; rights review pending",
  "Original training/data attribution: see docs/V4_ALL_MODEL_QA_TH.md and v4 package manifest",
  "Other engines install only as separate Universal .vwmodel v4 packages",
  "Wayu NC remains NonCommercial; model/distribution rights not altered by installation",
  "V4 QA assets have not yet been cleared for publication or commercial use"
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
Write-Output ("V4_DEFAULT_PACKAGE="+$makArchive)
Write-Output "V4_PROTOCOL=1"
Write-Output "V4_LEGACY_PACKAGE_SUPPORT=False"
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
