# VoxWeaveTTS v3 release checksum list. Only the audited v3 assets.
param([string]$Version = '0.11.0', [switch]$SkipOptionalPackages)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dist = Join-Path $root 'dist'
$names = @(
    ("VoxWeaveTTS-v{0}-portable.zip" -f $Version),
    'VoxWeaveTTS-TikTok-Extension-v0.2.5.zip'
)
if (!$SkipOptionalPackages) {
    $names += @(
      'ModelPackagesV3/VoxWeaveTTS-MakHam-Paradee-Thai-English-v1.0.0-format-v3.vwmodel',
      'ModelPackagesV3/VoxWeaveTTS-fastthaig2p-thai-som-0.3.0-format-v3.vwmodel',
      'ModelPackagesV3/VoxWeaveTTS-m2m100-418m-1.0.0-format-v3.vwmodel',
      'ModelPackagesV3/VoxWeaveTTS-melo-chinese-onnx-1.0.0-format-v3.vwmodel',
      'ModelPackagesV3/VoxWeaveTTS-supertonic3-multilingual-int8-1.0.0-format-v3.vwmodel',
      'ModelPackagesV3/CATALOG-v3.json'
    )
}
$lines = New-Object System.Collections.Generic.List[string]
foreach($name in $names) {
    $file = Join-Path $dist ($name.Replace('/', '\'))
    if(!(Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Missing v3 release asset: $name"
    }
    $sha = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    $filename = [IO.Path]::GetFileName($file)
    $lines.Add("$sha  $filename")
    Write-Output ("RELEASE_ASSET=$filename SHA256=$sha SIZE_BYTES="+(Get-Item $file).Length)
}
$out = Join-Path $dist ("SHA256SUMS-v{0}.txt" -f $Version)
[IO.File]::WriteAllLines($out, $lines.ToArray(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("RELEASE_CHECKSUMS=$out")
