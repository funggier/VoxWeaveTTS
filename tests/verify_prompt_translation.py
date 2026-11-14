"""Manual REAL Ollama verification of prompt-selected and explicitly selected languages.

Uses an already installed qwen3.5:4b, no model download, no settings changes,
and a one-minute keep-alive only for the requests in this script.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voxweavetts.ai_processing import DEFAULTS, process_ai, validate_settings
from voxweavetts.ollama_manager import model_status

model = "qwen3.5:4b"
base = "http://127.0.0.1:11434"
availability = model_status(model, base)
if not availability["server_running"] or not availability["selected"]["installed"]:
    print("Cannot test: Ollama model not installed", flush=True)
    sys.exit(2)

cases = [
    {
        "name": "prompt_japanese_when_target_unspecified",
        "text": "Good morning!",
        "target": "unspecified",
        "prompt": "Translate into polite Japanese. Output only the translation.",
        "required_script": r"[\u3040-\u30ff]",
        "excluded_script": r"[\u0e00-\u0e7f]",
    },
    {
        "name": "priority_english_over_custom_japanese",
        "text": "สวัสดีครับ",
        "target": "unspecified",
        "priority": "The output translation language is English.",
        "prompt": "Translate into Japanese, please.",
        "required_script": r"[A-Za-z]",
        "excluded_script": r"[\u0e00-\u0e7f\u3040-\u30ff]",
    },
    {
        "name": "explicit_thai_over_custom_japanese",
        "text": "The cat is sleeping on the chair.",
        "target": "th",
        "prompt": "Translate the message into Japanese.",
        "required_script": r"[\u0e00-\u0e7f]",
        "excluded_script": r"[\u3040-\u30ff]",
    },
]
passed_all = True
for item in cases:
    settings = validate_settings({
        **DEFAULTS,
        "enabled": True, "engine": "ollama", "model": model,
        "operation": "translate", "target_language": item["target"],
        "priority_instructions": item.get("priority", ""),
        "custom_prompt": item["prompt"], "keep_alive_minutes": 1,
        "timeout_seconds": 120,
    })
    start = time.monotonic()
    result = process_ai(item["text"], settings)
    output = result["text"]
    passed = (result["status"] == "processed"
              and re.search(item["required_script"], output) is not None
              and re.search(item["excluded_script"], output) is None)
    print(json.dumps({
        "name": item["name"], "original": item["text"],
        "result": output, "target_setting": item["target"],
        "status": result["status"], "passed": bool(passed),
        "elapsed_seconds": round(time.monotonic() - start, 2),
        "warning": result.get("warning"),
    }, ensure_ascii=False), flush=True)
    passed_all &= bool(passed)
sys.exit(0 if passed_all else 1)
