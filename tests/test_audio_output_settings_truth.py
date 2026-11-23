"""Output format report must describe the *current* Core selection, not stale PCM."""
from __future__ import annotations

from voxweavetts.audio_devices import WindowsDeviceOutput
from voxweavetts.computer_runtime import ComputerRuntime
import voxweavetts.computer_runtime as runtime_module


class Coordinator:
    def list(self):
        return []


class Sources:
    def status(self, mode):
        return {"mode": mode, "state": "idle", "pending": 0}


def test_actual_format_disappears_when_user_changes_rate_or_output(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runtime_module, "available_outputs",
        lambda: [{"id": "default", "label": "Default"},
                 {"id": "wasapi:DAC", "label": "DAC"}],
    )
    runtime = ComputerRuntime(
        port=8775, coordinator=Coordinator(), source_manager=Sources(),
        playback_state=object(), mode_path=tmp_path / "runtime.json",
        initial_mode="computer",
    )
    try:
        assert isinstance(runtime.output, WindowsDeviceOutput)
        with runtime._lock:
            runtime._output_id = "wasapi:DAC"
            runtime.output.last_format = {
                "device": "wasapi:DAC", "sample_rate": 192000,
                "channels": 2, "source_rate": 24000, "source_channels": 1,
                "buffer_ms": 50, "requested_rate": "auto",
                "requested_channels": "auto", "resampled": True,
            }
        assert runtime.snapshot()["actual_audio_format"]["source_rate"] == 24000
        changed = runtime.configure_audio(
            {"sample_rate": 48000, "channels": 2, "buffer_ms": 50})
        assert changed["audio_settings"]["sample_rate"] == 48000
        assert changed["actual_audio_format"] is None, (
            "Audio from an earlier 192k play must not look like the new 48k setting"
        )
        runtime.output.last_format = {
            "device": "wasapi:DAC", "sample_rate": 48000,
            "channels": 2, "source_rate": 24000, "source_channels": 1,
            "buffer_ms": 50, "requested_rate": 48000,
            "requested_channels": 2, "resampled": True,
        }
        assert runtime.snapshot()["actual_audio_format"]["sample_rate"] == 48000
        switched = runtime.configure_output("default")
        assert switched["output"] == "default"
        assert switched["actual_audio_format"] is None, (
            "Previous DAC format must not be reported for the default output"
        )
    finally:
        runtime.shutdown()