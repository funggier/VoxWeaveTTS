"""Native local-only v3 model file picker. No browser-supplied paths."""
from __future__ import annotations


class ModelPackageDialogUnavailable(RuntimeError):
    pass


def pick_model_file() -> str | None:
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
        return filedialog.askopenfilename(
            parent=root,
            title="VoxWeaveTTS - Install Offline v3 Model Package",
            filetypes=[("VoxWeaveTTS v3 Model Packages", "*.vwmodel")],
        ) or None
    except (OSError, RuntimeError, tk.TclError) as exc:
        raise ModelPackageDialogUnavailable("Windows native model picker unavailable") from exc
    finally:
        try:
            root.destroy()
        except (OSError, RuntimeError, tk.TclError):
            pass
