"""Manual REAL Ollama integration check (never run in CI automatically).

Usage: python tests/verify_live_translation.py
Requires local Ollama with qwen3.5:4b already installed.
Never downloads or changes saved AI settings; models stay loaded for 1 minute.
"""
import json
import re
import sys
import time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voxweavetts.ai_processing import DEFAULTS, process_ai, validate_settings
from voxweavetts.ollama_manager import model_status

MODEL = "qwen3.5:4b"
URL = "http://127.0.0.1:11434"
installed = model_status(MODEL, URL)
if not installed["server_running"] or not installed["selected"]["installed"]:
    print("Ollama/model not available; cannot verify real translation", flush=True)
    sys.exit(2)

cases = [
    ("en_to_th", "The cat is sleeping on the chair.", "th", ["แมว", "เก้าอี้"]),
    ("th_to_en", "แมวกำลังนอนอยู่บนเก้าอี้", "en", ["cat", "chair"]),
    ("mixed_to_th", "เกมนี้ is amazing!", "th", ["เกม"]),
    ("en_to_ja", "Good morning!", "ja", []),
    ("en_to_zh", "The sun is shining.", "zh", []),
    ("en_to_ko", "Thank you very much.", "ko", []),
]
all_ok = True
for label, original, target, keywords in cases:
    settings = validate_settings({
        **DEFAULTS, "enabled": True, "operation": "translate",
        "engine": "ollama", "model": MODEL, "ollama_base_url": URL,
        "target_language": target, "timeout_seconds": 120,
        "keep_alive_minutes": 1, "priority_instructions": "",
        "custom_prompt": "", "translation_mode": "whole_message",
    })
    start = time.monotonic()
    result = process_ai(original, settings)
    elapsed = round(time.monotonic() - start, 2)
    output = result["text"]
    scripts={"ja":r"[\u3040-\u30ff]", "zh":r"[\u3400-\u9fff]",
             "ko":r"[\uac00-\ud7af]"}
    passed = (result["status"] == "processed" and all(
        word in output.lower() for word in keywords
    ) and (target not in scripts or bool(re.search(scripts[target], output))))
    all_ok = all_ok and passed
    print(json.dumps({
        "test": label, "target": target,
        "original": original, "result": output,
        "status": result["status"], "warning": result.get("warning"),
        "semantic_keywords_matched": passed, "elapsed_seconds": elapsed,
    }, ensure_ascii=False), flush=True)
sys.exit(0 if all_ok else 1)
