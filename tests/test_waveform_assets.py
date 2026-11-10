"""Browser-only waveform asset delivery; no TTS engine or model required."""
from __future__ import annotations

import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from voxweavetts.server import Handler


class WaveformHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_browser_waveform_static_asset_and_controls(self):
        with urlopen(self.base + "/waveform_editor.js", timeout=5) as response:
            self.assertIn("javascript", response.headers["Content-Type"])
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            src = response.read().decode("utf-8")
            self.assertIn("VoxWaveformEditor", src)
            self.assertIn("PCM16", src)
        with urlopen(self.base + "/", timeout=5) as response:
            html = response.read().decode("utf-8")
            for expected in (
                'src="/waveform_editor.js"',
                'id="alignmentWaveform"',
                'id="alignmentZoom"',
                'id="alignmentPan"',
                'id="alignmentStart"',
                'id="alignmentEnd"',
            ):
                self.assertIn(expected, html)
            self.assertIn('touch-action:none', html)


if __name__ == "__main__":
    unittest.main()
