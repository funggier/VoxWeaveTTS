"""Exclusive local playback ownership shared by all engine-neutral work modes.

Changing a mode invalidates previous owner tokens and immediately clears the
single local OBS/PlaybackState. UI tabs are independent; TTS configuration and
pronunciation settings remain global. This is not authentication for LAN use.
"""
from __future__ import annotations

import secrets
import threading
from typing import Any

from .processing import InputError

MODES = ("studio", "reader", "queue", "live", "discord", "rules", "settings")


class ModeConflict(Exception):
    """A stale tab or non-active mode attempted to publish audio playback."""


class ModeState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active = "studio"
        self._token: str | None = None
        self._revision = 0
        self._changed = threading.Condition(self._lock)
        self._watchers = 0
        self._watcher_limit = 12

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_mode": self._active,
                "revision": self._revision,
                "exclusive_playback": True,
                "modes": list(MODES),
            }

    def activate(self, mode: Any, playback_state: Any) -> dict[str, Any]:
        if not isinstance(mode, str) or mode not in MODES:
            raise InputError("unknown workspace mode")
        with self._lock:
            self._revision += 1
            self._active = mode
            self._token = secrets.token_hex(16)
            # Hold ownership lock through invalidating the overlay so a
            # racing stale report cannot repopulate captions after switching.
            playback_state.reset()
            self._changed.notify_all()
            return {**self.snapshot(), "mode_token": self._token}

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
                self._revision > 0 and isinstance(mode, str)
                and isinstance(token, str)
                and mode == self._active
                and self._token is not None
                and secrets.compare_digest(self._token, token)
            )

    def report(self, payload: dict[str, Any], ready_job: Any,
               playback_state: Any) -> dict[str, Any]:
        with self._lock:
            if self._revision > 0 and (
                payload.get("mode") != self._active
                or payload.get("mode_token") != self._token
            ):
                raise ModeConflict("playback owner changed; activate current mode again")
            return playback_state.report(payload, ready_job=ready_job)