# Stop *only* processes owned by this VoxWeaveTTS installation, including
# orphaned Python/isolated TTS workers recorded by the runtime. Never stop
# Ollama, Unity, browsers or arbitrary processes just because they use Python.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\', '/')
$rootLower = $root.ToLowerInvariant()
$rootSlash = $rootLower + '\'
$registry = Join-Path $root 'runtime\processes'
$failed = $false

if (-not (Test-Path -LiteralPath (Join-Path $root 'src\voxweavetts\server.py') -PathType Leaf)) {
    Write-Error "Not a VoxWeaveTTS installation: $root"
    exit 2
}

Write-Output "[VoxWeaveTTS] Stop this installation: $root"
if ($DryRun) { Write-Output "[VoxWeaveTTS] DRY RUN: nothing will be terminated" }

$processList = @(Get-CimInstance Win32_Process)
$processes = @{}
foreach ($proc in $processList) {
    $processes[[int]$proc.ProcessId] = $proc
}
$owned = @{}
$recordPaths = New-Object System.Collections.ArrayList

# 1. Recorded ownership uses an exact OS process creation timestamp. An
#    obsolete PID file cannot kill an unrelated process with a reused PID.
if (Test-Path -LiteralPath $registry -PathType Container) {
    foreach ($file in @(Get-ChildItem -LiteralPath $registry -Filter '*.json' -File)) {
        try {
            if ($file.Length -gt 4096) { continue }
            $record = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($record.format -cne 'voxweavetts-owned-process-v1' -or
                ([string]$record.project_root).TrimEnd('\', '/').ToLowerInvariant() -ne $rootLower -or
                $record.kind -notin @('server','worker-host','worker-launcher') -or
                [int]$record.pid -le 0 -or
                [long]$record.created_filetime -le 0) {
                continue
            }
            $pidNumber = [int]$record.pid
            [void]$recordPaths.Add($file.FullName)
            $proc = $processes[$pidNumber]
            if ($null -eq $proc -or $proc.Name -notin @('python.exe','pythonw.exe','VoxWeaveTTS.exe')) {
                continue
            }
            try {
                $started = (Get-Process -Id $pidNumber -ErrorAction Stop).StartTime.ToUniversalTime().ToFileTimeUtc()
                if ([long]$started -eq [long]$record.created_filetime) {
                    $owned[$pidNumber] = "registered $($record.kind)"
                }
            } catch { }
        } catch {
            Write-Warning "Ignored invalid process marker: $($file.Name)"
        }
    }
}

# 2. Recovery for older installations that predate the registry. Only
#    VoxWeave Python interpreter/launcher paths INSIDE this exact folder match.
#    This does not select an external Python interpreter executing a different
#    app, or the process using port 8765 without verified project ownership.
foreach ($proc in $processList) {
    $name = [string]$proc.Name
    $line = [string]$proc.CommandLine
    $low = $line.ToLowerInvariant()
    if ($name -in @('python.exe','pythonw.exe')) {
        $projectInterpreter = (
            $low.Contains($rootSlash + '.venv\scripts\python.exe') -or
            $low.Contains($rootSlash + '.venv\scripts\pythonw.exe') -or
            $low.Contains($rootSlash + 'runtime\python\python.exe') -or
            $low.Contains($rootSlash + 'runtime\python\pythonw.exe') -or
            $low.Contains($rootSlash + 'runtime\engine-envs\')
        )
        $projectWorkerScript = (
            $low.Contains($rootSlash + 'extensions\engine-providers\') -and
            $low.Contains('\worker.py')
        )
        if ($projectInterpreter -and
            ($low -match '(?i)(?:^|\s)-m\s+voxweavetts(?:\.engine_worker_host)?(?:\s|$)' -or
             $projectWorkerScript)) {
            $owned[[int]$proc.ProcessId] = 'project Python launcher'
        }
    } elseif ($name -ieq 'VoxWeaveTTS.exe' -and
              $low.Contains($rootSlash + 'voxweavetts.exe')) {
        $owned[[int]$proc.ProcessId] = 'project portable launcher'
    }
}

# 3. Include descendants even when Windows venv spawns a Python executable
#    in a *shared* interpreter directory. They must descend from a verified
#    project process, not merely share a Python executable name.
$expanded = @{}
foreach ($id in @($owned.Keys)) { $expanded[[int]$id] = $true }
do {
    $changed = $false
    foreach ($proc in $processList) {
        $parent = [int]$proc.ParentProcessId
        $pidNumber = [int]$proc.ProcessId
        if ($expanded.ContainsKey($parent) -and -not $expanded.ContainsKey($pidNumber)) {
            $expanded[$pidNumber] = $true
            $changed = $true
        }
    }
} while ($changed)

$ordered = @($owned.Keys | ForEach-Object { [int]$_ } | Sort-Object)
if ($ordered.Count -eq 0) {
    Write-Output '[VoxWeaveTTS] No running owned processes found'
} else {
    foreach ($id in $ordered) {
        Write-Output ("[VoxWeaveTTS] Target PID={0}: {1}" -f $id, $owned[$id])
    }
    Write-Output ("[VoxWeaveTTS] Process tree includes {0} owned processes" -f $expanded.Count)
}

# Stop only topmost verified processes, so taskkill /T cleans up children,
# including real Python processes behind virtualenv launcher shims.
$roots = @($ordered | Where-Object {
    $ancestor = [int]$processes[$_].ParentProcessId
    -not $expanded.ContainsKey($ancestor)
})
# Some child processes also have explicit ownership records. They are already
# covered by the first tree's /T; only remaining live PID targets are killed.
if (-not $DryRun) {
    foreach ($id in @($roots + $ordered | Select-Object -Unique)) {
        if ($null -eq (Get-Process -Id $id -ErrorAction SilentlyContinue)) { continue }
        Write-Output "[VoxWeaveTTS] Force stopping PID=$id and descendants"
        & taskkill.exe /PID $id /T /F 2>&1 | ForEach-Object {
            Write-Output ("  " + $_)
        }
    }
    Start-Sleep -Milliseconds 400
    foreach ($id in $expanded.Keys) {
        if ($null -ne (Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue)) {
            Write-Warning "PID $id is still running (permission or external interference)"
            $failed = $true
        }
    }
    # This directory belongs to VoxWeaveTTS and stores only our PID markers.
    # Prune stale markers after ownership/time validation, never user settings.
    foreach ($file in $recordPaths) {
        try {
            $record = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
            $pidNumber = [int]$record.pid
            $proc = Get-Process -Id $pidNumber -ErrorAction SilentlyContinue
            if ($null -eq $proc -or
                $proc.StartTime.ToUniversalTime().ToFileTimeUtc() -ne [long]$record.created_filetime) {
                Remove-Item -LiteralPath $file -Force -ErrorAction Stop
            }
        } catch {
            Write-Warning "Could not clean stale marker $file"
        }
    }
}

# A localhost port can be occupied by some unrelated application: never kill
# it solely because it listens on 8765.
$port = @(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
if ($port.Count) {
    $portPid = [int]$port[0].OwningProcess
    if ($DryRun) {
        Write-Output "[VoxWeaveTTS] Port 8765 currently bound by PID=$portPid"
    } else {
        Write-Warning "Port 8765 is still listening (PID $portPid). It was not killed without verified ownership."
        if ($expanded.ContainsKey($portPid)) { $failed = $true }
    }
} elseif (-not $DryRun) {
    Write-Output '[VoxWeaveTTS] Port 8765 released'
}
if ($failed) {
    Write-Error '[VoxWeaveTTS] Stop incomplete; one or more owned processes remain'
    exit 1
}
if ($DryRun) {
    Write-Output '[VoxWeaveTTS] Dry-run complete'
} else {
    Write-Output '[VoxWeaveTTS] Stop complete: owned processes exited and Windows reclaims their memory/handles'
    Write-Output '[VoxWeaveTTS] Ollama, other Python projects, Unity and browsers were not targeted'
}
exit 0
