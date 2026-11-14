"""Manual real, offline M2M100 safetensors inference verification.

Run from a Python environment with optional torch/transformers/sentencepiece/
safetensors installed. Uses already installed local files only, no downloads.
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"src"))
from voxweavetts.ai_engine_registry import MODEL_DIR, m2m_info
from voxweavetts.ai_processing import DEFAULTS, process_ai, validate_settings

expected_sha="c061a21eec15453944783ceb4a13a216477dd4765c98fac10811818adf994968"
weights=MODEL_DIR/"model.safetensors"
if not weights.is_file() or not m2m_info().runtime_ready:
    print(json.dumps({"status":"unavailable","weight_exists":weights.exists(),
      "runtime_ready":m2m_info().runtime_ready}),flush=True)
    sys.exit(2)

start=time.monotonic()
digest=hashlib.file_digest(weights.open("rb"), "sha256").hexdigest()
if digest!=expected_sha:
    print("Official model safetensors SHA256 mismatch",digest,flush=True)
    sys.exit(3)
print("Verified official M2M100 safetensors SHA256",digest,"secs",round(time.monotonic()-start,2),flush=True)
cases=[
  ("en-th","The cat is sleeping on the chair.","en","th",r"[\u0e00-\u0e7f]",("แมว","เก้าอี้")),
  ("th-en","แมวกำลังนอนอยู่บนเก้าอี้","th","en",r"[a-zA-Z]",("cat","chair")),
  ("en-ja","Good morning.","en","ja",r"[\u3040-\u30ff\u3400-\u9fff]",("おはよう",)),
]
ok=True
for name,text,source,target,pattern,meaning_tokens in cases:
    config=validate_settings({**DEFAULTS,"enabled":True,
        "engine":"m2m100","operation":"translate","model":"",
        "source_language":source,"target_language":target,
        "auto_detect":False,"translation_mode":"whole_message"})
    t=time.monotonic()
    result=process_ai(text,config)
    script_ok=result["status"]=="processed" and re.search(pattern,result["text"]) is not None
    meaning_ok=all(token in result["text"].lower() for token in meaning_tokens)
    passed=bool(script_ok and meaning_ok)
    ok=ok and passed
    print(json.dumps({"name":name,"status":result["status"],"translation":result["text"],
       "script_ok":bool(script_ok),"meaning_keyword_ok":bool(meaning_ok),
       "passed":bool(passed),"seconds":round(time.monotonic()-t,2),
       "warning":result.get("warning")},ensure_ascii=False),flush=True)
sys.exit(0 if ok else 1)
