"""Conservative Windows memory-pressure signal for optional TTS Worker eviction.

Uses OS-reported *available* physical and commit headroom, not process RSS.
No background timer and no auto-unload if resources are healthy. Reports None
on unsupported platforms or API failures (fail open).
"""
from __future__ import annotations

import os
from typing import NamedTuple

# Workers may need >1 GB in addition to their model weights. Low commit can
# make even small ONNX allocations fail while physical RAM still exists.
MIN_AVAILABLE_COMMIT = 3 * 1024 ** 3
MIN_AVAILABLE_PHYSICAL = 1 * 1024 ** 3


class MemoryHeadroom(NamedTuple):
    physical_available: int
    commit_available: int

    @property
    def critical(self) -> bool:
        return (self.commit_available < MIN_AVAILABLE_COMMIT
                or self.physical_available < MIN_AVAILABLE_PHYSICAL)


def memory_headroom() -> MemoryHeadroom | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        result = MEMORYSTATUSEX()
        result.dwLength = ctypes.sizeof(result)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(result)):
            return None
        return MemoryHeadroom(int(result.ullAvailPhys),
                              int(result.ullAvailPageFile))
    except (OSError, AttributeError, ValueError):
        return None
