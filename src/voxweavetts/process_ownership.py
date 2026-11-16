"""Windows process ownership markers for explicit full-stop recovery.

Markers are per-instance and portable-relative under runtime/processes/.
They persist across unclean crashes so Stop-VoxWeaveTTS.cmd can recover
orphaned Python launchers/worker hosts without killing unrelated Python/Ollama.

A marker is *not* permission to kill a PID alone: the stopper also verifies
the OS process creation FILETIME, project root and expected VoxWeave process.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
TYPES = frozenset({"server", "worker-host", "worker-launcher"})


def windows_process_created_filetime(pid: int) -> int | None:
    """Return the OS-assigned creation FILETIME (100 ns since 1601 UTC)."""
    if os.name != "nt" or type(pid) is not int or pid <= 0:
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel_time), ctypes.byref(user_time),
        ):
            return None
        return (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
    finally:
        kernel.CloseHandle(handle)


def register_process(kind: str, *, pid: int | None = None,
                     root: Path = ROOT) -> bool:
    """Best-effort ownership record; model execution must never depend on it."""
    if kind not in TYPES:
        raise ValueError("unrecognized VoxWeave process kind")
    process_id = os.getpid() if pid is None else pid
    started = windows_process_created_filetime(process_id)
    if started is None:
        return False
    directory = Path(root).resolve() / "runtime" / "processes"
    record = {
        "format": "voxweavetts-owned-process-v1",
        "project_root": str(Path(root).resolve()),
        "kind": kind, "pid": process_id,
        "created_filetime": started,
    }
    try:
        directory.mkdir(parents=True, exist_ok=True)
        marker = directory / f"{kind}-{process_id}.json"
        temporary = directory / f"{kind}-{process_id}-{os.getpid()}.tmp"
        temporary.write_text(json.dumps(record, separators=(",", ":")),
                             encoding="utf-8")
        temporary.replace(marker)
        return True
    except OSError:
        return False
