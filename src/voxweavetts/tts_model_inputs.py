"""Private model-bound speech input for the local diagnostic UI.

Called after AI translation and post-translation pronunciation rules,
immediately before rendering. Mirrors VoiceEngine.generate(chunk, speed)
boundaries, including language-specific voice routing. Never include this
data in the ordinary public job status, events or subtitle timelines.
"""
from __future__ import annotations

from typing import Any


def collect_model_inputs(plan: dict[str, Any],
                         arguments: dict[str, Any]) -> list[dict[str, str]]:
    from .speech import _chunks

    default_engine = arguments["engine_id"]
    default_voice = arguments["voice_id"]
    routes = arguments.get("language_voice_routes")
    use_language_spans = routes is not None
    if use_language_spans:
        from .mixed_language import split_language_spans

    items: list[dict[str, str]] = []
    for segment in plan["segments"]:
        if segment["kind"] != "speech":
            # Silence and skip never call VoiceEngine.generate().
            continue
        spoken = segment["spoken_text"]
        if not spoken.strip():
            continue
        if use_language_spans:
            # The renderer splits by the same script-based boundaries and
            # chooses an explicit route or the current mode's default voice.
            spans = [(span.language, span.text)
                     for span in split_language_spans(spoken)
                     if span.text.strip()]
        else:
            spans = [("", spoken)]
        for language, span_text in spans:
            route = routes.get(language) if use_language_spans else None
            engine = route["engine_id"] if route else default_engine
            voice = route["voice_id"] if route else default_voice
            for chunk in _chunks(span_text):
                if chunk.strip():
                    items.append({
                        "language": language,
                        "engine_id": engine,
                        "voice_id": voice,
                        "text": chunk,
                    })
    return items
