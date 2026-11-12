"""Independent workspace ownership: switching tabs does not interrupt sources.

Each active mode has its own token, so two connected browser tabs cannot
silently claim the same source; distinct sources can run concurrently. Tokens
are ephemeral and are never returned in status or SSE snapshots.
"""
from __future__ import annotations

import secrets
import threading
from typing import Any

from .processing import InputError

MODES = ("studio", "reader", "queue", "live", "tiktok", "discord", "discord_client", "rules", "settings")


class ModeConflict(Exception):
    """A stale mode token attempted to mutate that mode or report playback."""


class ModeState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active = "studio"
        self._tokens: dict[str, str] = {}
        self._revision = 0
        self._changes: dict[str, int] = {}
        self._changed = threading.Condition(self._lock)
        self._watchers = 0
        self._watcher_limit = 12

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_mode": self._active,
                "revision": self._revision,
                "exclusive_playback": False,
                "concurrent_sources": True,
                "changed_mode": max(self._changes, key=self._changes.get) if self._changes else None,
                "mode_revisions": dict(self._changes),
                "modes": list(MODES),
            }

    def activate(self, mode: Any, playback_state: Any) -> dict[str, Any]:
        if not isinstance(mode, str) or mode not in MODES:
            raise InputError("unknown workspace mode")
        with self._lock:
            self._revision += 1
            self._active = mode
            self._tokens[mode] = secrets.token_hex(16)
            self._changes[mode] = self._revision
            # No playback reset: other sources must keep running and reporting
            # their actual playback clocks when a mode gains focus.
            self._changed.notify_all()
            return {**self.snapshot(), "mode_token": self._tokens[mode]}

    def subscribe(self) -> None:
        with self._lock:
            if self._watchers >= self._watcher_limit:
                raise ModeConflict("too many local mode watchers")
            self._watchers += 1

    def unsubscribe(self) -> None:
        with self._lock:
            self._watchers = max(0, self._watchers - 1)

    def watch(self, previous_revision: int, timeout: float = 1.0) -> dict[str, Any] | None:
        if type(previous_revision) is not int or previous_revision < 0:
            raise ValueError("invalid mode revision")
        if not 0 < timeout <= 5:
            raise ValueError("invalid mode watcher timeout")
        with self._changed:
            result = self.snapshot()
            if result["revision"] != previous_revision:
                return result
            self._changed.wait(timeout)
            result = self.snapshot()
            return result if result["revision"] != previous_revision else None

    def is_owner(self, mode: object, token: object) -> bool:
        with self._lock:
            return (
                isinstance(mode, str) and isinstance(token, str)
                and mode in self._tokens
                and secrets.compare_digest(self._tokens[mode], token)
            )

    def report(self, payload: dict[str, Any], ready_job: Any,
               playback_state: Any) -> dict[str, Any]:
        with self._lock:
            # Preserve the legacy loopback-only reporting path until a
            # browser first registers workspace capabilities.
            if self._tokens and not self.is_owner(
                payload.get("mode"), payload.get("mode_token")
            ):
                raise ModeConflict("playback owner changed for this workspace")
            if getattr(playback_state, "supports_modes", False):
                return playback_state.report(
                    payload, ready_job=ready_job,
                    workspace=payload.get("mode") or "studio")
            return playback_state.report(payload, ready_job=ready_job)
