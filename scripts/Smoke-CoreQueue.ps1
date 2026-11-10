# End-to-end local test: no external services and no file uploads.
# Requires Start-Dev.cmd and one installed Thai Engine.
param([int]$Port=8765)
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$base="http://127.0.0.1:$Port"
$engines=(Invoke-RestMethod "$base/v1/engines" -TimeoutSec 5).engines
$engine=$engines | Where-Object {$_.assets_ready -and $_.runtime_ready} | Select-Object -First 1
if(-not $engine){throw "No ready TTS Engine; run scripts/Install-ThaiEngine.ps1"}
$body=@{
  text="สวัสดีครับ 55555"
  source="queue-smoke"
  source_message_id=("test-"+[guid]::NewGuid().ToString("N"))
  engine_id=$engine.id
  voice_id=$engine.voice_id
  speed=1.0
  rules=@(@{match="555";match_mode="five_run";mode="replace";spoken="ฮ่า ฮ่า ฮ่า"})
} | ConvertTo-Json -Depth 8
$bytes=[Text.Encoding]::UTF8.GetBytes($body)
$job=Invoke-RestMethod "$base/v1/jobs" -Method Post -ContentType "application/json; charset=utf-8" -Headers @{"X-VoxWeaveTTS-Intent"="queue-speech"} -Body $bytes -TimeoutSec 8
if(-not $job.speech_id){throw "Job ID not received"}
$id=$job.speech_id
Write-Output ("QUEUED "+$id+" engine="+$engine.id)
$completed=$false
for($i=0; $i -lt 80; $i++){
  $status=Invoke-RestMethod "$base/v1/jobs/$id" -TimeoutSec 5
  if($status.state -eq "ready"){$completed=$true;break}
  if($status.state -in @("failed","cancelled")){throw ("Job ended with "+$status.state)}
  Start-Sleep -Milliseconds 250
}
if(-not $completed){throw "Timed out waiting for a ready WAV"}
$events=(Invoke-RestMethod "$base/v1/jobs/$id/events" -TimeoutSec 5).events
if($events[-1].type -ne "speech.ready"){throw "Missing ready event"}
if($status.display_text -ne "สวัสดีครับ 55555"){throw "Subtitle mismatch"}
$destination=Join-Path $root "output\engine-neutral-queue-smoke.wav"
Invoke-WebRequest "$base/v1/jobs/$id/audio" -UseBasicParsing -OutFile $destination -TimeoutSec 5 | Out-Null
$wav=[IO.File]::ReadAllBytes($destination)
if($wav.Length -lt 44 -or [Text.Encoding]::ASCII.GetString($wav,0,4) -ne "RIFF"){throw "Invalid WAV"}
Write-Output ("PASS: job="+$id+" states="+(($events|ForEach-Object {$_.type}) -join ",")+" bytes="+$wav.Length)
