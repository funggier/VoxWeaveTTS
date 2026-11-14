# Build a Windows self-contained ZIP. Never include local user data, logs or secrets.
param([string]$Version = '0.5.2', [switch]$SkipZip)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venv=Join-Path $root '.venv\Scripts\python.exe'
$site=Join-Path $root '.venv\Lib\site-packages'
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework/v4.0.30319/csc.exe'
if (!(Test-Path $venv) -or !(Test-Path $compiler)) {throw 'Windows build prerequisites missing'}
if (!(Test-Path (Join-Path $site 'onnxruntime')) -or !(Test-Path (Join-Path $site 'pythaitts'))) {throw 'TTS runtime prerequisites missing'}
& $venv -c 'import grpc,google.protobuf'
if ($LASTEXITCODE -ne 0) {throw 'YouTube streamList requires grpcio and protobuf in the build venv'}
$pythonHome=(& $venv -c 'import sys; print(sys.base_prefix)').Trim()
if ($LASTEXITCODE -ne 0 -or !(Test-Path (Join-Path $pythonHome 'LICENSE.txt'))) {throw 'Python runtime not found'}

$stage=Join-Path $root 'dist\VoxWeaveTTS'
$zip=Join-Path $root ("dist\VoxWeaveTTS-v{0}-portable.zip" -f $Version)
if (Test-Path $stage) {Remove-Item -LiteralPath $stage -Recurse -Force}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

function Copy-Tree([string]$source,[string]$destination,[string[]]$skip=@()) {
  if (!(Test-Path $source)) {throw "Required input missing: $source"}
  New-Item -ItemType Directory -Force -Path $destination | Out-Null
  $opts=@($source,$destination,'/E','/NFL','/NDL','/NJH','/NJS','/NP',
          '/XD','__pycache__','.git','.venv','tests','test','.pytest_cache',
          '/XF','*.pyc','*.pyo')+$skip
  & robocopy @opts | Out-Null
  if ($LASTEXITCODE -ge 8) {throw "File copy failed: $source"}
}
Copy-Tree (Join-Path $root 'src') (Join-Path $stage 'src')
Copy-Tree (Join-Path $root 'web') (Join-Path $stage 'web')
# Include the manually-installed Chrome extension in the portable distribution.
Copy-Tree (Join-Path $root 'extensions') (Join-Path $stage 'extensions')
Copy-Tree (Join-Path $root 'docs') (Join-Path $stage 'docs')
foreach ($name in @('LICENSE','README_TH.md','README.md')) {
  Copy-Item (Join-Path $root $name) (Join-Path $stage $name) -Force
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
# Freeze package dependencies but never copy arbitrary pretrained model weights
# or private voice files from the development environment.
Copy-Tree $site (Join-Path $runtime 'Lib\site-packages') @('*.onnx','*.npy','*.pt','*.pth','*.wav','*.mp3','*.flac')
$modelDir=Join-Path $stage 'models\makham-paradee'
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
foreach ($name in @('paradee_thai_int8.onnx','config.json')) {
  $from=Join-Path $root ("models\makham-paradee\{0}" -f $name)
  if (!(Test-Path $from)) {throw "Missing approved MakHam model file: $name"}
  Copy-Item $from (Join-Path $modelDir $name) -Force
}
foreach ($dir in @('presets','models\packages','models\fastthaig2p','cache\temp','cache\torch',
                   'cache\huggingface','voices','output','logs','data\settings',
                   'data\reading','data\filters','data\dictionaries',
                   'data\presets','data\profiles','config')) {
  New-Item -ItemType Directory -Force -Path (Join-Path $stage $dir) | Out-Null
}
$hash=(Get-FileHash (Join-Path $modelDir 'paradee_thai_int8.onnx') -Algorithm SHA256).Hash
$notice=@(
  "VoxWeaveTTS v$Version third-party notices",
  "VoxWeaveTTS: MIT; see LICENSE.",
  "Bundled Python 3.11: PSF license; see runtime/python/LICENSE.txt.",
  "PyThaiTTS 1.0.0: Apache-2.0; https://pypi.org/project/PyThaiTTS/",
  "grpcio: Apache-2.0; https://github.com/grpc/grpc",
  "Google Protocol Buffers: BSD-3-Clause; https://github.com/protocolbuffers/protobuf",
  "MakHam Paradee INT8 model: Apache-2.0; https://huggingface.co/pythainlp/MakHamTTS",
  "Model SHA256: $hash",
  "Training dataset credit: https://huggingface.co/datasets/pythainlp/MakHamTTS-dataset",
  "Authors: PyThaiNLP / Wannaphong Phatthiyaphaibun; Paradee / Sahil Mahendrakar",
  "Third-party Python package license metadata/files are in runtime/python/Lib/site-packages/*dist-info/.",
  "User-generated speech, recordings and chat messages have their own rights.",
  "Only MakHam Paradee weights are bundled. Other models are optional .vwmodel packages.",
  "FastThaiG2P 325MB model, personal voices and private local settings are NOT bundled."
)
$notice | Set-Content (Join-Path $stage 'THIRD_PARTY_NOTICES.txt') -Encoding UTF8

$exe=Join-Path $stage 'VoxWeaveTTS.exe'
& $compiler /nologo /target:winexe /platform:x64 ("/out:"+$exe) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll (Join-Path $root 'scripts\VoxWeaveTTS.Launcher.cs')
if ($LASTEXITCODE -ne 0 -or !(Test-Path $exe)) {throw 'Windows launcher compile failed'}

$launcher=Join-Path $stage 'Start-Console.cmd'
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
'@ | Set-Content -LiteralPath $launcher -Encoding Ascii

Write-Output ("PORTABLE_STAGE="+$stage)
Write-Output ("PORTABLE_MODEL_SHA256="+$hash)
Write-Output ("PORTABLE_EXE="+$exe)
if (!$SkipZip) {
  if (Test-Path $zip) {Remove-Item $zip -Force}
  Compress-Archive -LiteralPath $stage -DestinationPath $zip -CompressionLevel Optimal
  if (!(Test-Path $zip)) {throw 'Portable ZIP was not built'}
  $size=[math]::Round((Get-Item $zip).Length/1MB,1)
  $sha=(Get-FileHash $zip -Algorithm SHA256).Hash
  Write-Output ("PORTABLE_ZIP="+$zip)
  Write-Output ("PORTABLE_ZIP_MB="+$size)
  Write-Output ("PORTABLE_ZIP_SHA256="+$sha)
}
