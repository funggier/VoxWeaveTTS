"""Concurrent media clocks with a backward-compatible primary OBS subtitle.

Each workspace reports its own HTMLMediaElement clock independently. The
existing OBS overlay displays the most recent audible source, while API
snapshots additionally expose all live mode subtitles for multi-panel overlays.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from .playback_state import PlaybackState, StreamFull
from .processing import InputError


class PlaybackHub:
    supports_modes = True

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._changed = threading.Condition(self._lock)
        self._states: dict[str, PlaybackState] = {}
        self._updated: dict[str, float] = {}
        self._started: dict[str, float] = {}
        self._revisions: dict[str, int] = {}
        self._revision = 0
        self._subscribers = 0
        self._last_mode: str | None = None

    def report(self, data: dict[str, Any], *, ready_job: dict[str, Any] | None = None,
               workspace: str) -> dict[str, Any]:
        if not isinstance(workspace, str) or not workspace:
            raise InputError("workspace required for playback report")
        with self._changed:
            state = self._states.setdefault(workspace, PlaybackState())
            state.report(data, ready_job=ready_job)
            self._revisions[workspace] = state.snapshot()["revision"]
            self._last_mode = workspace
            self._updated[workspace] = time.monotonic()
            if data.get("event") == "start":
                self._started[workspace] = self._updated[workspace]
            self._revision += 1
            self._changed.notify_all()
            return self._snapshot()

    def _snapshot(self, mode: str = "segment") -> dict[str, Any]:
        snapshots = {name: state.snapshot(mode) for name, state in self._states.items()}
        for name, snapshot in snapshots.items():
            before = self._revisions.get(name, 0)
            if snapshot["revision"] != before:
                # Detect stale-clock transitions for clients watching the hub.
                if name in self._revisions:
                    self._revision += 1
                self._revisions[name] = snapshot["revision"]
        live = [name for name, state in snapshots.items()
                if state["state"] in ("playing", "paused")]
        active = [name for name in live if snapshots[name]["state"] == "playing"]
        primary_name = (
            max(active, key=lambda name:self._started.get(name,0))
            if active else
            max(live, key=lambda name:self._started.get(name,0))
            if live else self._last_mode
        )
        if primary_name is None:
            selected = PlaybackState().snapshot(mode)
        else:
            selected = snapshots[primary_name]
        return {
            **selected,
            "revision": self._revision,
            "workspace": primary_name,
            "active_modes": active,
            "subtitles_by_mode": {name:state["subtitle"] for name,state in snapshots.items()
                                  if state["state"] == "playing"},
            "concurrent_playback": True,
        }

    def snapshot(self, mode: str = "segment") -> dict[str, Any]:
        with self._changed:
            return self._snapshot(mode)

    def reset(self, workspace: str | None = None) -> None:
        with self._changed:
            if workspace is None:
                self._states.clear()
                self._updated.clear()
                self._started.clear()
                self._revisions.clear()
                self._last_mode = None
            else:
                self._states.pop(workspace, None)
                self._updated.pop(workspace, None)
                self._started.pop(workspace, None)
                self._revisions.pop(workspace, None)
                if self._last_mode == workspace:
                    self._last_mode = None
            self._revision += 1
            self._changed.notify_all()

    def subscribe(self) -> None:
        with self._lock:
            if self._subscribers >= 8:
                raise StreamFull("too many local overlay viewers")
            self._subscribers += 1

    def unsubscribe(self) -> None:
        with self._lock:
            self._subscribers = max(0, self._subscribers - 1)

    def watch(self, previous_revision: int, timeout: float = 1.0,
              mode: str = "segment") -> dict[str, Any] | None:
        if type(previous_revision) is not int or previous_revision < 0:
            raise ValueError("invalid playback revision")
        if not 0 < timeout <= 5:
            raise ValueError("invalid playback watcher timeout")
        with self._changed:
            snapshot = self._snapshot(mode)
            if snapshot["revision"] != previous_revision:
                return snapshot
            self._changed.wait(timeout)
            snapshot = self._snapshot(mode)
            return snapshot if snapshot["revision"] != previous_revision else None
