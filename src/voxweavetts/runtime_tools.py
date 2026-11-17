"""Resolve managed runtime tools from the portable folder before system PATH."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_uv(root: Path) -> str | None:
    folder = Path(root) / "runtime" / "tools"
    candidate = folder / ("uv.exe" if os.name == "nt" else "uv")
    if (folder.is_dir() and not folder.is_symlink()
        and candidate.is_file() and not candidate.is_symlink()
        and candidate.resolve().parent == folder.resolve()):
        return str(candidate)
    return shutil.which("uv")
