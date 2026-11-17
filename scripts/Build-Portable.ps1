# Build a Windows self-contained ZIP. Never include local user data, logs or secrets.
param([string]$Version = '0.9.4', [switch]$SkipZip)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venv=Join-Path $root '.venv\Scripts\python.exe'
$site=Join-Path $root '.venv\Lib\site-packages'
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework/v4.0.30319/csc.exe'
if (!(Test-Path $venv) -or !(Test-Path $compiler)) {throw 'Windows build prerequisites missing'}
if (!(Test-Path (Join-Path $site 'onnxruntime')) -or !(Test-Path (Join-Path $site 'pythaitts'))) {throw 'TTS runtime prerequisites missing'}
& $venv -c 'import grpc,google.protobuf,kokoro_onnx,phonemizer,espeakng_loader; from pathlib import Path; from espeakng_loader import get_library_path,get_data_path; assert Path(get_library_path()).is_file(); assert Path(get_data_path()).is_dir()'
if ($LASTEXITCODE -ne 0) {throw 'Portable build requires grpc, protobuf, Kokoro ONNX, phonemizer, espeakng-loader DLL and dictionaries'}
# A Japanese Kokoro voice is not usable with eSpeak alone. Validate the
# bundled MeCab dictionary and Misaki G2P before distributing Portable.
& $venv -c 'from misaki import ja; import unidic_lite; p,_=ja.JAG2P()(chr(0x591a)+chr(0x5206)+chr(0x6bbb)+chr(0x3054)+chr(0x3068)+chr(0x98df)+chr(0x3063)+chr(0x3066)+chr(0x308b)+chr(0x3082)+chr(0x3093)+chr(0x306d)); assert p and len(p)<100'
if ($LASTEXITCODE -ne 0) {throw 'Portable build requires misaki[ja]==0.8.0 and unidic-lite==1.0.8 for Kokoro Japanese speech'}
& $venv -c 'import sherpa_onnx; assert sherpa_onnx.OfflineTtsSupertonicModelConfig'
if ($LASTEXITCODE -ne 0) {throw 'Portable build requires sherpa-onnx==2.0.1 for Chinese/Korean/31-language add-on models'}
$pythonHome=(& $venv -c 'import sys; print(sys.base_prefix)').Trim()
if ($LASTEXITCODE -ne 0 -or !(Test-Path (Join-Path $pythonHome 'LICENSE.txt'))) {throw 'Python runtime not found'}

$stage=Join-Path $root 'dist\VoxWeaveTTS'
$zip=Join-Path $root ("dist\VoxWeaveTTS-v{0}-portable.zip" -f $Version)
if (Test-Path $stage) {Remove-Item -LiteralPath $stage -Recurse -Force}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

function Copy-Tree([string]$source,[string]$destination,[string[]]$skip=@(),[string[]]$skipDirs=@()) {
  if (!(Test-Path $source)) {throw "Required input missing: $source"}
  New-Item -ItemType Directory -Force -Path $destination | Out-Null
  $opts=@($source,$destination,'/E','/NFL','/NDL','/NJH','/NJS','/NP',
          '/XD','__pycache__','.git','.venv','tests','test','.pytest_cache')+$skipDirs+
          @('/XF','*.pyc','*.pyo')+$skip
  & robocopy @opts | Out-Null
  if ($LASTEXITCODE -ge 8) {throw "File copy failed: $source"}
}
Copy-Tree (Join-Path $root 'src') (Join-Path $stage 'src')
Copy-Tree (Join-Path $root 'web') (Join-Path $stage 'web')
# Include the manually-installed Chrome extension in the portable distribution.
Copy-Tree (Join-Path $root 'extensions') (Join-Path $stage 'extensions') -skipDirs @('engine-providers')
# External executable providers are local, explicitly trusted plug-ins: never
# publish approved worker code or private provider metadata by accident.
Copy-Tree (Join-Path $root 'docs') (Join-Path $stage 'docs')
if (!(Test-Path (Join-Path $stage 'docs\third-party\ESPEAK_NG_GPL-3.0.txt'))) {throw 'Missing GPL-3.0 text for bundled eSpeak NG runtime'}
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
# Optional M2M100 development runtime is deliberately excluded from the
# basic portable ZIP. Its 418M weights and torch/transformers dependencies
# remain user-installed add-ons; Ollama needs no embedded ML dependencies.
Copy-Tree $site (Join-Path $runtime 'Lib\site-packages') @('*.onnx','*.npy','*.pt','*.pth','*.wav','*.mp3','*.flac') @(
  'torch','torchgen','functorch','transformers','tokenizers','safetensors',
  'sentencepiece','sympy','networkx',
  'torch-*.dist-info','transformers-*.dist-info','tokenizers-*.dist-info',
  'safetensors-*.dist-info','sentencepiece-*.dist-info',
  'sympy-*.dist-info','networkx-*.dist-info'
)
# MakHam is a BUILT-IN ENGINE with a REMOVABLE MODEL PACKAGE. Supply
# its official data-only .vwmodel in the release and preinstall a copy into
# the packaged models registry. Never bake the weights into program code.
$makArchive=Join-Path $root 'dist\ModelPackages\VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0.vwmodel'
$makSource=Join-Path $root 'models\makham-paradee'
if ((Test-Path (Join-Path $makSource 'paradee_thai_int8.onnx')) -and
    (Test-Path (Join-Path $makSource 'config.json'))) {
  $env:PYTHONPATH=Join-Path $root 'src'
  & $venv -m voxweavetts.model_packages pack-makham --source $makSource --output $makArchive
  if ($LASTEXITCODE -ne 0) {throw 'Could not build verified MakHam .vwmodel'}
}
if (!(Test-Path $makArchive)) {throw 'MakHam restore .vwmodel missing'}
$env:PYTHONPATH=Join-Path $root 'src'
& $venv -c 'import sys; from pathlib import Path; from voxweavetts.model_packages import install_model_package; install_model_package(Path(sys.argv[1]), base=Path(sys.argv[2]))' $makArchive (Join-Path $stage 'models\packages')
if ($LASTEXITCODE -ne 0) {throw 'Could not preinstall MakHam .vwmodel into Portable'}
$modelDir=Join-Path $stage 'models\packages\makham-paradee\1.0.0'
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'models\recovery-packages') | Out-Null
Copy-Item $makArchive (Join-Path $stage 'models\recovery-packages\VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0.vwmodel') -Force
foreach ($dir in @('presets','models\packages','models\fastthaig2p','cache\temp','cache\torch',
                   'cache\huggingface','voices','output','logs','data\settings',
                   'data\reading','data\filters','data\dictionaries',
                   'data\presets','data\profiles','models\ai','models\ai\packages','models\ai\m2m100_418m','config')) {
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
  "Kokoro-ONNX v0.6.0: https://github.com/thewh1teagle/kokoro-onnx (license in site-packages).",
  "Japanese Kokoro G2P: Misaki 0.8.0 (Apache-2.0), https://github.com/hexgrad/misaki; requires fugashi, jaconv, mojimoji and UniDic Lite (their individual license metadata are bundled).",
  "sherpa-onnx 2.0.1: Apache-2.0 runtime (see bundled dist-info licenses), https://github.com/k2-fsa/sherpa-onnx.",
  "Optional Chinese MeloTTS model: MIT model-card license; source https://huggingface.co/myshell-ai/MeloTTS-Chinese; review separate voice and training rights.",
  "Optional Supertonic 3 model: BigScience OpenRAIL-M with use restrictions, NOT MIT despite MIT sample code; source https://huggingface.co/Supertone/supertonic-3. Model pack includes full license.",
  "Optional Wayu Paxa Edge: CC BY-NC 4.0 - noncommercial use ONLY, original 12 voices; distributed as a SEPARATE optional .vwmodel with upstream notices. It is NOT in this Portable ZIP. https://huggingface.co/wayu-ai/wayu-paxa-tts-edge",
  "Kokoro-82M multilingual model: Apache-2.0 upstream; installed separately as .vwmodel; rights to voices/training require review.",
  "eSpeak NG DLL/data: GPL-3.0, source https://github.com/espeak-ng/espeak-ng; full GPL text in docs/third-party/ESPEAK_NG_GPL-3.0.txt. Redistributors must follow source and notice obligations.",
  "phonemizer: https://github.com/bootphon/phonemizer (license in bundled package metadata).",
  "Third-party Python package license metadata/files are in runtime/python/Lib/site-packages/*dist-info/.",
  "User-generated speech, recordings and chat messages have their own rights.",
  "MakHam Paradee is a built-in Engine with PREINSTALLED removable .vwmodel weights in models/packages/makham-paradee/1.0.0. A standalone recovery .vwmodel is included in models/recovery-packages. Removing the model leaves the Engine installed; shared TTS runtimes are managed separately.",
  "Other model packages: FastThaiG2P, Vachana, Kokoro, MeloTTS Chinese, Supertonic 3, Wayu NC (separate archive), experimental M2M100.",
  "FastThaiG2P 325MB model, personal voices and private local settings are NOT bundled."
)
$notice | Set-Content (Join-Path $stage 'THIRD_PARTY_NOTICES.txt') -Encoding UTF8

$exe=Join-Path $stage 'VoxWeaveTTS.exe'
& $compiler /nologo /target:winexe /platform:x64 ("/out:"+$exe) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll (Join-Path $root 'scripts\VoxWeaveTTS.Launcher.cs')
if ($LASTEXITCODE -ne 0 -or !(Test-Path $exe)) {throw 'Windows launcher compile failed'}

# Ship the same force-stop utility in every portable build. It stops ONLY
# processes proven to belong to the extracted installation.
New-Item -ItemType Directory -Path (Join-Path $stage 'scripts') -Force | Out-Null
Copy-Item (Join-Path $root 'Stop-VoxWeaveTTS.cmd') (Join-Path $stage 'Stop-VoxWeaveTTS.cmd') -Force
Copy-Item (Join-Path $root 'scripts\Stop-VoxWeaveTTS.ps1') (Join-Path $stage 'scripts\Stop-VoxWeaveTTS.ps1') -Force
# The Engine Provider UI installs isolated runtimes using the trusted recipe
# directory under scripts/engine-dependencies; include it in the ZIP so an
# extracted Portable can install/repair providers without the source checkout.
Copy-Tree (Join-Path $root 'scripts\engine-dependencies') (Join-Path $stage 'scripts\engine-dependencies')
Copy-Item (Join-Path $root 'scripts\Install-EngineProvider.ps1') (Join-Path $stage 'scripts\Install-EngineProvider.ps1') -Force
Copy-Item (Join-Path $root 'scripts\Install-WayuWorker.ps1') (Join-Path $stage 'scripts\Install-WayuWorker.ps1') -Force
# M2M100 weights are a separate data-only .vwmodel; its heavy Torch runtime is
# installed only with opt-in into a separate local Python environment.
Copy-Tree (Join-Path $root 'scripts\ai-dependencies') (Join-Path $stage 'scripts\ai-dependencies')
Copy-Item (Join-Path $root 'scripts\Install-M2M100Runtime.ps1') (Join-Path $stage 'scripts\Install-M2M100Runtime.ps1') -Force
if (!(Test-Path (Join-Path $stage 'scripts\ai-dependencies\m2m100.txt'))) {
  throw 'Portable missing trusted M2M100 runtime recipe'
}
foreach ($required in @('pythaitts.txt','vachana.txt','kokoro.txt','sherpa.txt','wayu-nc.txt')) {
  if (!(Test-Path (Join-Path $stage ("scripts\engine-dependencies\{0}" -f $required)))) {
    throw "Portable missing trusted worker recipe: $required"
  }
}
@'
@echo off
call "%~dp0Stop-VoxWeaveTTS.cmd" %*
exit /b %ERRORLEVEL%
'@ | Set-Content -LiteralPath (Join-Path $stage 'Stop-Console.cmd') -Encoding Ascii

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
  # Windows PowerShell Compress-Archive holds large in-memory ZIP structures
  # for the embedded Python runtime and can consume multiple GiB. The Windows
  # built-in bsdtar creates the same standard .zip with bounded memory.
  if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
    & tar.exe -a -c -f $zip -C (Join-Path $root 'dist') 'VoxWeaveTTS'
    if ($LASTEXITCODE -ne 0) {throw 'Portable ZIP packaging with tar.exe failed'}
  } else {
    Compress-Archive -LiteralPath $stage -DestinationPath $zip -CompressionLevel Optimal
  }
  if (!(Test-Path $zip) -or (Get-Item $zip).Length -lt 1MB) {throw 'Portable ZIP was not built'}
  $size=[math]::Round((Get-Item $zip).Length/1MB,1)
  $sha=(Get-FileHash $zip -Algorithm SHA256).Hash
  Write-Output ("PORTABLE_ZIP="+$zip)
  Write-Output ("PORTABLE_ZIP_MB="+$size)
  Write-Output ("PORTABLE_ZIP_SHA256="+$sha)
}
