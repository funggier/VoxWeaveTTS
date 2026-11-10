# Local HTTP end-to-end smoke test. Start-Dev.cmd must be running first.
# Generated WAVs remain in ignored output/. Does not modify user presets.
param([int]$Port=8765)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$base = "http://127.0.0.1:$Port"
$engines = Invoke-RestMethod "$base/v1/engines" -TimeoutSec 5
if ($engines.engines.Count -lt 2) { throw "Expected at least 2 registered engines" }
if ($null -eq $engines.control_schema.post.pitch_semitones) { throw "Missing DSP control schema" }
$out = Join-Path $root "output\voice-studio-smoke"
New-Item -ItemType Directory -Force -Path $out | Out-Null
foreach ($engine in $engines.engines) {
    if (-not ($engine.assets_ready -and $engine.runtime_ready)) {
        Write-Output ("SKIP " + $engine.id + ": assets/runtime not installed")
        continue
    }
    $settings = @{
        text = "สวัสดีครับ วันนี้เรากำลังทดสอบเสียงภาษาไทย"
        engine_id = $engine.id
        voice_id = $engine.voice_id
        seed = 100
        speed = 1.05
        rules = @()
        pronunciations = @{}
        voice_controls = @{
            gain_db = 2
            pitch_semitones = -1
            bass_db = 2
            treble_db = -1
            formant_preserve = $true
        }
    }
    $payload = $settings | ConvertTo-Json -Depth 10
    $target = Join-Path $out ($engine.id + ".wav")
    Invoke-WebRequest "$base/v1/speech" -Method Post -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($payload)) -OutFile $target -UseBasicParsing -TimeoutSec 30 | Out-Null
    $header = [IO.File]::ReadAllBytes($target)
    if ($header.Length -lt 100 -or [Text.Encoding]::ASCII.GetString($header,0,4) -ne "RIFF") {
        throw "Invalid WAV from $($engine.id)"
    }
    Write-Output ("PASS " + $engine.id + " WAV bytes=" + $header.Length +
                  " sha256=" + (Get-FileHash -Algorithm SHA256 $target).Hash)
}
