param([string]$Version = '0.9.4')
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dist = Join-Path $root 'dist'
$files = @(
    ("VoxWeaveTTS-v{0}-portable.zip" -f $Version),
    'VoxWeaveTTS-TikTok-Extension-v0.2.5.zip',
    'ModelPackages/VoxWeaveTTS-FastThaiG2P-ThaiSom-v0.3.0.vwmodel',
    'ModelPackages/VoxWeaveTTS-Vachana-Thai-4Voices-v1.0.0.vwmodel',
    'ModelPackages/VoxWeaveTTS-Kokoro82M-Multilingual-INT8-v1.0.0.vwmodel',
    'ModelPackages/VoxWeaveTTS-MeloTTS-Chinese-ONNX-v1.0.0.vwmodel',
    'ModelPackages/VoxWeaveTTS-Supertonic3-31Languages-INT8-v1.0.0.vwmodel',
    'ModelPackages/VoxWeaveTTS-Wayu-Paxa-Edge-Thai-English-12Voices-NC-v1.0.0.vwmodel',
    'VoxWeaveTTS-M2M100-418M-v1.0.0.vwmodel'
)
$lines = New-Object System.Collections.Generic.List[string]
foreach ($name in $files) {
    $src = Join-Path $dist ($name.Replace('/', '\'))
    if (!(Test-Path -LiteralPath $src -PathType Leaf)) {throw ("Missing v$Version Release asset: $name")}
    $digest = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant()
    $fileName = [IO.Path]::GetFileName($src)
    $lines.Add(("$digest  $fileName"))
    Write-Output ("VERIFIED_ASSET=$fileName SHA256=$digest SIZE_BYTES=$((Get-Item -LiteralPath $src).Length)")
}
$manifest=Join-Path $dist ("SHA256SUMS-v{0}.txt" -f $Version)
[IO.File]::WriteAllLines($manifest, $lines.ToArray(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("CHECKSUMS_FILE=$manifest")
