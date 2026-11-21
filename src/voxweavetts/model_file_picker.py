"""Native local-only v4 model file picker. No browser-supplied paths."""
from __future__ import annotations


class ModelPackageDialogUnavailable(RuntimeError):
    pass


def pick_model_file() -> str | None:
    files = _pick_model_files(multiple=False)
    return files[0] if files else None


def pick_model_files() -> tuple[str, ...]:
    return _pick_model_files(multiple=True)


def _pick_model_files(*, multiple: bool) -> tuple[str, ...]:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
    except Exception as exc:
        raise ModelPackageDialogUnavailable("Windows native model picker unavailable") from exc
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        options = {
            "parent": root,
            "title": "VoxWeaveTTS - Install Offline v4 Model Packages",
            "filetypes": [("VoxWeaveTTS v4 Model Packages", "*.vwmodel")],
        }
        if multiple:
            return root.tk.splitlist(filedialog.askopenfilenames(**options))
        file = filedialog.askopenfilename(**options)
        return (file,) if file else ()
    except (OSError, RuntimeError, tk.TclError) as exc:
        raise ModelPackageDialogUnavailable("Windows native model picker unavailable") from exc
    finally:
        try:
            root.destroy()
        except (OSError, RuntimeError, tk.TclError):
            pass
