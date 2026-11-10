<#
Install the optional Thai CPU ONNX engine into a project-local development venv.
Prerequisites: uv and GitHub CLI (gh), with Internet access for the first install.
This script NEVER uploads voice samples. It keeps model files below models/.
This is not yet the final no-Python portable application.
#>
param([switch]$SkipModel)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
  foreach ($dir in @("cache\uv","cache\pip","cache\huggingface","cache\temp","models\fastthaig2p","models\makham-paradee")) {
    New-Item -Path $dir -ItemType Directory -Force | Out-Null
  }
  $env:UV_CACHE_DIR = Join-Path $root "cache\uv"
  $env:UV_LINK_MODE = "copy"
  $env:PIP_CACHE_DIR = Join-Path $root "cache\pip"
  $env:HF_HOME = Join-Path $root "cache\huggingface"
  $env:TORCH_HOME = Join-Path $root "cache\torch"
  $env:TEMP = Join-Path $root "cache\temp"
  $env:TMP = $env:TEMP

  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required for this development installer; see https://docs.astral.sh/uv/"
  }
  $python = Join-Path $root ".venv\Scripts\python.exe"
  if (-not (Test-Path $python)) {
    & uv venv --python 3.11 .venv
    if ($LASTEXITCODE -ne 0) { throw "uv venv failed" }
  }
  & uv pip install --python $python --link-mode copy "pythaitts==1.0.0"
  if ($LASTEXITCODE -ne 0) { throw "uv pip install failed" }

  # PyThaiTTS includes a compact (~8.5 MB) MakHam Paradee ONNX file.
  # Copy it into our portable project model directory, without network calls.
  $packageSource = & $python -c "import pathlib,pythaitts.pretrained.makham.paradee_tts as m; print(pathlib.Path(m.__file__).parent / 'data')"
  if ($LASTEXITCODE -ne 0) { throw "Unable to find MakHam Paradee packaged assets" }
  $paradeeSource = $packageSource.Trim()
  $paradeeTarget = Join-Path $root "models\makham-paradee"
  foreach ($name in @("paradee_thai_int8.onnx", "config.json")) {
    $origin = Join-Path $paradeeSource $name
    if (-not (Test-Path -LiteralPath $origin)) { throw "Missing packaged Paradee asset $name" }
    Copy-Item -LiteralPath $origin -Destination (Join-Path $paradeeTarget $name) -Force
  }
  Write-Output "Prepared MakHam Paradee local CPU Engine from the installed package."

  if (-not $SkipModel) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
      throw "GitHub CLI (gh) is required for model download; see https://cli.github.com/"
    }
    $target = Join-Path $root "models\fastthaig2p"
    $expected = @{ "kokoro_thai.onnx"=325563297; "thai_som.npy"=522368; "config.json"=2516 }
    $ready = $true
    foreach ($key in $expected.Keys) {
      $f = Join-Path $target $key
      if (-not (Test-Path $f) -or (Get-Item $f).Length -ne $expected[$key]) {
        $ready = $false
      }
    }
    if (-not $ready) {
      & gh release download v0.3.0 --repo awslabs/FastThaiG2P --dir $target --pattern "kokoro_thai.onnx" --pattern "thai_som.npy" --pattern "config.json" --clobber
      if ($LASTEXITCODE -ne 0) { throw "Model download failed" }
    }
    foreach ($key in $expected.Keys) {
      $f = Join-Path $target $key
      if (-not (Test-Path $f) -or (Get-Item $f).Length -ne $expected[$key]) {
        throw "Missing or invalid asset: $key"
      }
      Write-Output ((Get-FileHash -Algorithm SHA256 $f).Hash + "  " + $key)
    }
  }
  $env:PYTHONPATH = Join-Path $root "src"
  & $python -c "from voxweavetts.speech import list_engine_info; [print(e.as_dict()) for e in list_engine_info()]"
  if ($LASTEXITCODE -ne 0) { throw "Engine self-check failed" }
  Write-Output "Thai engine development setup completed."
}
finally { Pop-Location }