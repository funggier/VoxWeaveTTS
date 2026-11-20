"""Offline v4 translation worker, independent from VoxWeaveTTS Core.

The model lives in assets/, the Python runtime lives alongside this worker
in the v4 isolated environment. Input text is always data, not instructions.
No network, tools or prompt execution paths are available to this worker.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
import os
import sys
from pathlib import Path

MAX_LINE = 65_536
MAX_TEXT = 5_000
VERSION = 1


class Translator:
    def __init__(self, root: Path):
        self.root = root
        spec = json.loads((root / "plugin" / "adapter.json").read_text("utf-8"))
        if (not isinstance(spec, dict)
            or set(spec) != {"backend", "languages"}
            or spec["backend"] != "m2m100-transformers-v1"):
            raise ValueError("unsupported v4 translation plugin")
        self.languages = set(spec["languages"])
        self.tokenizer = None
        self.model = None

    def _load(self) -> None:
        if self.model is not None:
            return
        import torch
        from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
        torch.set_num_threads(min(2, max(1, os.cpu_count() or 2)))
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
        torch.set_grad_enabled(False)
        folder = str(self.root / "assets")
        tokenizer = M2M100Tokenizer.from_pretrained(folder, local_files_only=True)
        model = M2M100ForConditionalGeneration.from_pretrained(
            folder, local_files_only=True, use_safetensors=True).eval()
        self.tokenizer = tokenizer
        self.model = model

    def translate(self, text: str, source: str, target: str) -> str:
        if (not isinstance(text, str) or not text.strip()
            or len(text) > MAX_TEXT or "\0" in text
            or not isinstance(source, str) or not isinstance(target, str)
            or source not in self.languages or target not in self.languages):
            raise ValueError("unsupported translation input/language")
        if source == target:
            return text
        self._load()
        self.tokenizer.src_lang = source
        tokens = self.tokenizer(text, return_tensors="pt", truncation=False)
        if tokens["input_ids"].shape[-1] > 512:
            raise ValueError("too many M2M source tokens")
        output = self.model.generate(
            **tokens,
            forced_bos_token_id=self.tokenizer.get_lang_id(target),
            max_new_tokens=192, num_beams=4, early_stopping=False,
            do_sample=False,
        )
        strings = self.tokenizer.batch_decode(output, skip_special_tokens=True)
        if not strings or not isinstance(strings[0], str):
            raise ValueError("empty translation")
        return strings[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    args = parser.parse_args()
    os.environ.update({
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TOKENIZERS_PARALLELISM": "false",
    })
    translator = Translator(Path(args.model_dir))
    while True:
        raw = sys.stdin.buffer.readline(MAX_LINE + 1)
        if not raw:
            break
        if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
            break
        request_id = None
        try:
            r = json.loads(raw.decode("utf-8"))
            if not isinstance(r, dict) or set(r) != {
                "version", "request_id", "method", "text", "model",
                "source_language", "target_language",
            }:
                raise ValueError("invalid translation request")
            request_id = r["request_id"]
            if (r["version"] != VERSION or r["method"] != "translate"
                or type(request_id) is not int or request_id < 1
                or not isinstance(r["model"], str) or len(r["model"]) > 110):
                raise ValueError("invalid translation IPC protocol")
            with redirect_stdout(sys.stderr):
                result = translator.translate(
                    r["text"], r["source_language"], r["target_language"])
            reply = {
                "version": VERSION, "request_id": request_id,
                "ok": True, "text": result,
            }
        except (OSError, ValueError, RuntimeError, ImportError, KeyError,
                TypeError, MemoryError) as exc:
            reason = str(exc).lower()
            exhausted = (isinstance(exc, MemoryError) or
                         "out of memory" in reason or "1455" in reason)
            print("v4 translation worker:", type(exc).__name__, file=sys.stderr)
            reply = {"version": VERSION, "request_id": request_id,
                     "ok": False,
                     "error": "resource_exhausted" if exhausted else "inference_failed"}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
