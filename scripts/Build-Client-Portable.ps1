# Build the independent, model-free Windows Remote Client ZIP.
param(
    [string]$Version = '0.12.13',
    [switch]$SkipZip,
    [string]$StageDirectory = ''
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dist = Join-Path $root 'dist'
$stage = if ($StageDirectory) { [IO.Path]::GetFullPath($StageDirectory) }
         else { Join-Path $dist 'VoxWeaveTTS-Client' }
if (!$stage.StartsWith(($dist.TrimEnd('\')+'\'),[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Client stage must be inside dist/'
}
if (!$SkipZip -and (Split-Path $stage -Leaf) -ne 'VoxWeaveTTS-Client') {
    throw 'Client ZIP staging folder must be named VoxWeaveTTS-Client'
}
$zip = Join-Path $dist ("VoxWeaveTTS-Client-v{0}-portable.zip" -f $Version)
if (!$SkipZip -and (Test-Path -LiteralPath $zip)) {
    throw 'Client ZIP exists; refusing to overwrite'
}
$venv = Join-Path $root '.venv\Scripts\python.exe'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
if (!(Test-Path $venv) -or !(Test-Path $compiler)) {
    throw 'Client packaging requires local Python venv and Windows C# compiler'
}
$pythonHome=(& $venv -c 'import sys; print(sys.base_prefix)').Trim()
if ($LASTEXITCODE -ne 0 -or !(Test-Path (Join-Path $pythonHome 'LICENSE.txt'))) {
    throw 'Embedded CPython distribution missing'
}
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'src\voxweavetts') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'data') | Out-Null
$runtime=Join-Path $stage 'runtime\python'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
foreach ($name in @('python.exe','pythonw.exe','python311.dll','python3.dll',
                    'vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt')) {
    $from=Join-Path $pythonHome $name
    if (Test-Path $from) { Copy-Item $from (Join-Path $runtime $name) -Force }
}
function Copy-PortableTree([string]$from, [string]$to, [string[]]$excludeDirs=@()) {
    New-Item -ItemType Directory -Force -Path $to | Out-Null
    & robocopy $from $to /E /NFL /NDL /NJH /NJS /NP /XD '__pycache__' 'site-packages' @excludeDirs /XF '*.pyc' '*.pyo' | Out-Null
    if ($LASTEXITCODE -ge 8) { throw 'Portable Python standard library copy failed' }
}
Copy-PortableTree (Join-Path $pythonHome 'Lib') (Join-Path $runtime 'Lib')
Copy-PortableTree (Join-Path $pythonHome 'DLLs') (Join-Path $runtime 'DLLs')
Copy-PortableTree (Join-Path $pythonHome 'tcl') (Join-Path $runtime 'tcl')
New-Item -ItemType Directory -Force -Path (Join-Path $runtime 'Lib\site-packages') | Out-Null
Copy-Item (Join-Path $root 'src\voxweavetts\__init__.py') (Join-Path $stage 'src\voxweavetts\__init__.py') -Force
Copy-Item (Join-Path $root 'src\voxweavetts\remote_client.py') (Join-Path $stage 'src\voxweavetts\remote_client.py') -Force
Copy-Item (Join-Path $root 'LICENSE') (Join-Path $stage 'LICENSE') -Force
Copy-Item (Join-Path $root 'docs\REMOTE_CONTROL_CLIENT_TH.md') (Join-Path $stage 'README_TH.md') -Force
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'config') | Out-Null
Copy-Item (Join-Path $root 'config\client-connection.examples.jsonc') (Join-Path $stage 'config\client-connection.examples.jsonc') -Force
@'
@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
set "PYTHONNOUSERSITE=1"
set "PYTHONDONTWRITEBYTECODE=1"
start "" "%CD%\runtime\python\pythonw.exe" -m voxweavetts.remote_client
endlocal
'@ | Set-Content (Join-Path $stage 'Start-Client.cmd') -Encoding Ascii
@(
  'VoxWeaveTTS Remote Client - third-party notices',
  'VoxWeaveTTS Python source: see LICENSE',
  'Embedded CPython: Python Software Foundation License; runtime/python/LICENSE.txt',
  'This client contains no TTS engines, model files, or server runtime components.'
) | Set-Content (Join-Path $stage 'THIRD_PARTY_NOTICES.txt') -Encoding UTF8
& $compiler /nologo /target:winexe /platform:x64 ("/out:"+(Join-Path $stage 'VoxWeaveTTS-Client.exe')) /reference:System.Windows.Forms.dll (Join-Path $root 'scripts\VoxWeaveTTS.ClientLauncher.cs')
if ($LASTEXITCODE -ne 0) {throw 'Client GUI launcher compilation failed'}
$env:PYTHONPATH=Join-Path $stage 'src'
$env:PYTHONNOUSERSITE='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& (Join-Path $runtime 'python.exe') -X utf8 -c 'import tkinter; import voxweavetts.remote_client; assert voxweavetts.remote_client.RemoteAPI'
if ($LASTEXITCODE -ne 0) {throw 'Standalone Client Python import validation failed'}
if (Test-Path (Join-Path $stage 'models')) {throw 'Model assets leaked into client'}
$files=@(Get-ChildItem (Join-Path $stage 'src') -Recurse -File)
if ($files.Count -ne 2) {throw 'Extra server source leaked into client'}
Write-Output ("CLIENT_PORTABLE_STAGE="+$stage)
Write-Output 'CLIENT_MODEL_PACKAGES=0'
Write-Output 'CLIENT_THIRD_PARTY_PYTHON_DEPENDENCIES=0'
if (!$SkipZip) {
    & tar.exe -a -c -f $zip -C (Split-Path $stage -Parent) (Split-Path $stage -Leaf)
    if ($LASTEXITCODE -ne 0 -or !(Test-Path $zip)) {throw 'Client ZIP creation failed'}
    Write-Output ("CLIENT_PORTABLE_ZIP="+$zip)
    Write-Output ("CLIENT_PORTABLE_SHA256="+(Get-FileHash $zip -Algorithm SHA256).Hash)
}
$global:LASTEXITCODE=0
