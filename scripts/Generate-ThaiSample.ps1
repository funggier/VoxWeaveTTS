# Run Start-Dev.cmd first, then run this example to generate output/api_demo.wav.
param([int]$Port=8765)
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$out=Join-Path $root "output\api_demo.wav"
New-Item -Path (Split-Path $out) -ItemType Directory -Force | Out-Null
$request=@{
 text="ชายหนุ่มผู้นี้บรรลุขั้นอมตะ แต่คำต้องห้ามไม่ควรอ่าน"
 speed=1.0
 engine_id="fastthaig2p-cpu"
 voice_id="thai_som"
 rules=@(@{match="คำต้องห้าม";mode="silence";display="***";silence_ms=400})
 pronunciations=@{"อมตะ"="อะ มะ ตะ"}
} | ConvertTo-Json -Depth 8
$bytes=[Text.Encoding]::UTF8.GetBytes($request)
Invoke-WebRequest -Uri "http://127.0.0.1:$Port/v1/speech" -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes -OutFile $out -UseBasicParsing
Write-Output "Saved $out"
