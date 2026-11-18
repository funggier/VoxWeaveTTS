"""First-party dependency/rights review state for optional runtimes.

Operational readiness, SHA verification and commercial/distribution permission
are distinct. These policies are app-owned metadata, never inferred from
untrusted model manifests or user-provided wheelhouse names.

This is a conservative review *status*, not an automated license ruling.
Changing a hold requires updating source and reviewing actual artifacts.
"""
from __future__ import annotations

import re
from typing import Any

# These are REVIEW BLOCKERS for new first-party *offline wheelhouse publication*.
# Existing installed runtimes and published first-party locks remain usable;
# runtime lifecycle must not be coupled to licensing review metadata.
_HOLDS: dict[str, dict[str, Any]] = {
    "wayu-nc": {
        "commercial_status": "noncommercial-only",
        "model_license": "CC-BY-NC-4.0",
        "code_license": "Apache-2.0 (upstream inference claim)",
        "reasons": (
            "wayu-weight-noncommercial-license",
            "remote-vcs-and-direct-url-recipe",
            "third-party-runtime-rights-not-cleared",
        ),
        "description": (
            "Wayu Paxa Edge model weights are CC BY-NC 4.0 (noncommercial). "
            "Inference source is separately licensed; current runtime recipe "
            "contains Git/direct URL dependencies and is not an audited offline lock."
        ),
    },
    "vachana": {
        "commercial_status": "review-required",
        "model_license": "MIT (model-card claim; review required)",
        "code_license": "unverified for vachanatts 0.0.7 wheel",
        "reasons": (
            "vachanatts-wheel-no-license-declaration",
            "vachanatts-wheel-missing-license-text",
            "third-party-notice-review",
        ),
        "description": (
            "The candidate vachanatts 0.0.7 wheel lacks a sufficient license "
            "declaration/license text. A model card's MIT claim does not grant "
            "rights to redistribute that independent runtime artifact."
        ),
    },
    "kokoro": {
        "commercial_status": "review-required",
        "model_license": "model-specific; review required",
        "code_license": "contains GPL-3.0-or-later dependency",
        "reasons": (
            "phonemizer-gpl-3-or-later-compliance-review",
            "espeakng-loader-native-license-review",
            "third-party-notice-review",
        ),
        "description": (
            "Candidate Kokoro runtime includes phonemizer (GPLv3 or later) "
            "and espeakng-loader native binaries requiring compliance review. "
            "GPL does not prohibit commercial use but redistribution has obligations."
        ),
    },
}
_REVIEW = {
    "commercial_status": "review-required",
    "model_license": "model-specific; verify separately",
    "code_license": "review each dependency and bundled binary",
    "reasons": ("third-party-distribution-audit-not-final",),
    "description": (
        "A working or hash-verified runtime is not a commercial-rights "
        "or redistribution clearance."
    ),
}
_IDS = frozenset(("wayu-nc", "vachana", "kokoro",
                 "pythaitts", "sherpa", "m2m100"))
_GUIDE = "docs/PROVIDER_RIGHTS_READINESS_TH.md"
_EXTERNAL_ID = re.compile(r"[a-z][a-z0-9-]{2,31}\Z")


def review(runtime_id: str, *, approved_external: bool = False) -> dict[str, Any]:
    """Return a fresh JSON-safe read-only snapshot with no file/network IO."""
    if not isinstance(runtime_id, str) or not (
        runtime_id in _IDS or
        (approved_external and bool(_EXTERNAL_ID.fullmatch(runtime_id)))
    ):
        raise ValueError("unknown trusted runtime ID")
    data = _HOLDS.get(runtime_id, _REVIEW)
    return {
        "review_version": 1,
        "runtime_id": runtime_id,
        "publication_state": (
            "hold" if runtime_id in _HOLDS else "review-required"
        ),
        "commercial_status": data["commercial_status"],
        "model_license": data["model_license"],
        "code_license": data["code_license"],
        "reasons": list(data["reasons"]),
        "description": data["description"],
        "reference": _GUIDE,
        "legal_clearance": False,
        # None is undetermined/manual review, not permission granted.
        "offline_wheelhouse_release_allowed": (
            False if runtime_id in _HOLDS else None
        ),
    }


def require_first_party_wheelhouse_publication(runtime_id: str) -> None:
    """Prevent accidentally promoting a currently blocked draft to trusted.

    This applies ONLY to release curation, not a user's existing runtime,
    personal noncommercial use, model install, or the read-only audit.
    Review and update this source policy after provenance/license resolution.
    """
    status = review(runtime_id)
    if status["publication_state"] == "hold":
        raise ValueError(
            runtime_id + ": first-party offline wheelhouse publication is "
            "on HOLD pending license, provenance and dependency review; "
            "see " + _GUIDE
        )
