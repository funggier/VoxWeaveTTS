"""VoxWeaveTTS Universal v4 Windows SAPI speech worker (original MIT code).

Requires a locally installed Windows SAPI desktop voice and Windows PowerShell 5.1.
No voice files, third-party runtimes or online calls are bundled. The PowerShell
program is fixed source; user text is transferred only as JSON over stdin.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
import os
from pathlib import Path
import subprocess
import sys

SAMPLE_RATE = 16_000
MAX_PCM_BYTES = 32_000_000
VOICES = {"system_default", "system_female", "system_male"}

# Powershell is invoked with a static encoded program rather than interpolating
# user text into command-line arguments or executable source.
_PS_PROGRAM = r'''
$ErrorActionPreference = 'Stop'
$synth = $null
$stream = $null
try {
    [Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $inputJson = [Console]::In.ReadToEnd()
    $request = ConvertFrom-Json -InputObject $inputJson -ErrorAction Stop
    Add-Type -AssemblyName System.Speech -ErrorAction Stop
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $installed = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled })
    if ($installed.Count -eq 0) { throw 'no enabled Windows desktop speech voice' }
    $gender = switch ([string]$request.voice) {
        'system_female' { 'Female' }
        'system_male' { 'Male' }
        default { '' }
    }
    if ($gender) {
        $selected = $installed | Where-Object {
            $_.VoiceInfo.Gender.ToString() -eq $gender
        } | Select-Object -First 1
        if ($null -ne $selected) {
            $synth.SelectVoice($selected.VoiceInfo.Name)
        }
    }
    # SAPI rate is not a physical playback speed multiplier.
    $rate = [Math]::Round(([Math]::Min(5.0,
             [Math]::Max(0.5, [double]$request.speed)) - 1.0) * 2.5)
    $synth.Rate = [int][Math]::Max(-10, [Math]::Min(10, $rate))
    $stream = New-Object System.IO.MemoryStream
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        16000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono)
    $synth.SetOutputToAudioStream($stream, $format)
    # This is plain text (not SpeakSsml); no SSML or command interpretation.
    $synth.Speak([string]$request.text)
    $audio = $stream.ToArray()
    if ($audio.Length -lt 2 -or $audio.Length -gt 32000000 -or
        ($audio.Length % 2) -ne 0) {
        throw 'invalid PCM audio length'
    }
    [Console]::Write([Convert]::ToBase64String($audio))
} catch {
    [Console]::Error.WriteLine('windows_sapi_unavailable')
    exit 1
} finally {
    if ($null -ne $synth) { $synth.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
}
'''


def powershell_path() -> Path:
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    exe = system / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not exe.is_file():
        raise RuntimeError("Windows PowerShell 5.1 unavailable")
    return exe


def synthesize(request: dict) -> dict:
    if (not isinstance(request, dict) or request.get("version") != 1
        or request.get("method") != "synthesize"
        or type(request.get("request_id")) is not int
        or request.get("voice_id") not in VOICES):
        raise ValueError("unsupported SAPI request")
    text = request.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("invalid text")
    speed = float(request.get("speed", 1.0))
    if not math.isfinite(speed) or not 0.5 <= speed <= 5:
        raise ValueError("invalid speed")
    fixed_program = base64.b64encode(_PS_PROGRAM.encode("utf-16le")).decode("ascii")
    payload = json.dumps(
        {"text": text, "voice": request["voice_id"], "speed": speed},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    try:
        proc = subprocess.run(
            [str(powershell_path()), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-EncodedCommand", fixed_program],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            timeout=105, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            raise RuntimeError("Windows SAPI failed")
        audio = base64.b64decode(proc.stdout.strip(), validate=True)
    except (OSError, subprocess.TimeoutExpired, ValueError, binascii.Error) as exc:
        raise RuntimeError("Windows SAPI failed") from exc
    if not audio or len(audio) > MAX_PCM_BYTES or len(audio) % 2:
        raise RuntimeError("Windows SAPI invalid output")
    return {
        "version": 1, "request_id": request["request_id"],
        "ok": True, "sample_rate": SAMPLE_RATE,
        "pcm16_b64": base64.b64encode(audio).decode("ascii"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.parse_args()
    for line in sys.stdin:
        request_id = None
        try:
            if len(line) > 40_000:
                raise ValueError("oversized request")
            request = json.loads(line)
            if isinstance(request, dict):
                request_id = request.get("request_id")
            reply = synthesize(request)
        except Exception:
            reply = {
                "version": 1, "request_id": request_id,
                "ok": False, "error": "synthesis_failure",
            }
        sys.stdout.write(json.dumps(reply, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
