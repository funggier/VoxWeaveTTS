"""First-party distribution checks for unchanged model weights plus v4 runtimes.

Independent operational facts:
- A user can select and install a local, validated v4 archive in one click.
- Package model-weight terms and runtime dependency terms are distinct.
- All eight v4 model weight sets are SHA-256 identical to previously
  published v2 assets, and five are identical to previously published v3.
- The new v4 Worker/wheel redistributions require their own license notices.
- A NonCommercial model is in scope for this non-commercial-first project;
  a commercial license is not required to consider non-commercial release.

This read-only module is NOT consulted as an installation allow-list and
never converts user-provided manifest claims into legal clearance.
"""
from __future__ import annotations

import re
from typing import Any

_GUIDE = "docs/V4_RIGHTS_REVIEW_TH.md"
_PACKAGE_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")

# These are app-curated REVIEW notes, not legal opinions or package permissions.
# Changing one to 'cleared' would require review of the exact binary artifacts,
# full model/dataset provenance, wheel source/license notices and obligations.
KNOWN_V4_MODELS: dict[str, dict[str, Any]] = {
    "makham-paradee": {
        "kind": "tts", "model_license": "Apache-2.0",
        "upstream": "https://huggingface.co/pythainlp/MakHamTTS",
        "state": "review-required", "commercial": "review-required",
        "reasons": ("makham-dataset-attribution-cc-by-4.0",
                    "pythaitts-runtime-dependencies-need-notice-audit"),
    },
    "fastthaig2p-thai-som": {
        "kind": "tts", "model_license": "Apache-2.0 (package declaration)",
        "upstream": "https://github.com/awslabs/FastThaiG2P",
        "state": "review-required", "commercial": "review-required",
        "reasons": ("fastthai-training-and-weight-provenance-review",
                    "pythaitts-runtime-dependencies-need-notice-audit"),
    },
    "melo-chinese-onnx": {
        "kind": "tts", "model_license": "MIT",
        "upstream": "https://huggingface.co/myshell-ai/MeloTTS-Chinese",
        "state": "review-required", "commercial": "review-required",
        "reasons": ("onnx-conversion-provenance-and-notices-review",
                    "offline-native-wheel-notices-review"),
    },
    "supertonic3-multilingual-int8": {
        "kind": "tts", "model_license": "OpenRAIL-M",
        "upstream": "https://huggingface.co/Supertone/supertonic-3",
        "state": "review-required", "commercial": "review-required",
        "reasons": ("openrail-m-use-restrictions-and-redistribution-notices",
                    "onnx-conversion-and-wheel-notices-review"),
    },
    "kokoro-multilingual-int8": {
        "kind": "tts", "model_license": "Apache-2.0",
        "upstream": "https://huggingface.co/hexgrad/Kokoro-82M",
        "state": "hold", "commercial": "review-required",
        "reasons": ("phonemizer-gpl-3-or-later-compliance-review",
                    "espeakng-loader-native-binary-source-and-notices-review",
                    "multilingual-g2p-derivative-license-review"),
    },
    "vachana-thai-four-voices": {
        "kind": "tts", "model_license": "MIT",
        "upstream": "https://huggingface.co/VIZINTZOR/VachanaTTS",
        "state": "hold", "commercial": "review-required",
        "reasons": ("vachanatts-0.0.7-wheel-no-license-declaration",
                    "vachanatts-wheel-missing-license-text",
                    "model-training-data-and-third-party-notices-review"),
    },
    "wayu-paxa-edge-nc": {
        "kind": "tts", "model_license": "CC-BY-NC-4.0",
        "upstream": "https://huggingface.co/wayu-ai/wayu-paxa-tts-edge",
        "state": "hold", "commercial": "noncommercial-only",
        "reasons": ("weights-cc-by-nc-4.0-prohibit-commercial-use",
                    "wayu-research-acceptable-use-conditions",
                    "106-wheel-and-native-binary-compliance-review"),
    },
    "m2m100-418m": {
        "kind": "translation", "model_license": "MIT",
        "upstream": "https://huggingface.co/facebook/m2m100_418M",
        "state": "review-required", "commercial": "review-required",
        "reasons": ("model-training-provenance-review",
                    "transformers-torch-safetensors-wheel-license-audit"),
    },
}


def review(package_id: str) -> dict[str, Any]:
    """Return independent, immutable-source v4 review status for one package.

    Unknown future package IDs are never prevented from being user-installed
    by this module; unknown *first-party publication* remains blocked.
    """
    if not isinstance(package_id, str) or not _PACKAGE_ID.fullmatch(package_id):
        raise ValueError("invalid v4 package id")
    note = KNOWN_V4_MODELS.get(package_id)
    if note is None:
        return {
            "review_version": 4, "package_id": package_id,
            "package_kind": "unknown", "upstream_model_license": "unverified",
            "upstream": None, "publication_state": "review-required",
            "commercial_status": "review-required",
            "reasons": ["unknown-third-party-package-requires-independent-review"],
            "public_release_allowed": False, "legal_clearance": False,
            "user_installs_offline_without_license_server": True,
            "user_install_is_redistribution_clearance": False,
            "release_intent": "noncommercial-first; original upstream terms",
            "original_weight_files_sha_identical_to_published_v2": False,
            "new_v4_runtime_license_review_pending": True,
            "commercial_clearance_required_for_nc_release": False,
            "reference": _GUIDE,
        }
    return {
        "review_version": 4, "package_id": package_id,
        "package_kind": note["kind"],
        "upstream_model_license": note["model_license"],
        "upstream": note["upstream"],
        "publication_state": note["state"],
        "commercial_status": note["commercial"],
        "reasons": list(note["reasons"]),
        "public_release_allowed": False, "legal_clearance": False,
        "user_installs_offline_without_license_server": True,
        "user_install_is_redistribution_clearance": False,
        "release_intent": "noncommercial-first; original upstream terms",
        "original_weight_files_sha_identical_to_published_v2": True,
        "new_v4_runtime_license_review_pending": True,
        "commercial_clearance_required_for_nc_release": False,
        "weight_provenance_report": "docs/v4_weight_continuity_summary.json",
        "reference": _GUIDE,
    }


def require_first_party_publication(package_id: str) -> None:
    """Block v4 first-party model distribution until independently cleared.

    A package's own manifest is untrusted for legal clearance and never
    overrides these app-maintained release gates.
    """
    record = review(package_id)
    if not record["public_release_allowed"]:
        raise ValueError(
            f"{package_id}: first-party v4 model publication blocked: "
            f"{record['publication_state']}; see {_GUIDE}"
        )
