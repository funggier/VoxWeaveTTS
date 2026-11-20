"""Universal v4 relocation contracts: all executable paths follow the Portable."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxweavetts import universal_model_v4 as v4
from test_v4_plugin_packages import fixture


class V4RelocatableTests(unittest.TestCase):
    def test_python_plugin_resolves_new_path_after_portable_move(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            archive=fixture(folder/"package")
            source=folder/"source-validation"
            destination=folder/"relocated-validation"
            exe=source/"runtime/python/python.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"fake-python-for-path-resolution")
            with patch.object(v4,"sys_platform",return_value="windows-x64"):
                result=v4.install(archive,root=source)
            manifest,_=v4.for_engine(result["engine_id"],root=source)
            self.assertTrue(v4.ready(source,manifest))
            old=v4.worker_command(source,manifest)
            self.assertTrue(old[0].startswith(str(source)))
            self.assertTrue(old[-1].startswith(str(source)))
            source.rename(destination)
            moved,_=v4.for_engine(result["engine_id"],root=destination)
            self.assertTrue(v4.ready(destination,moved))
            new=v4.worker_command(destination,moved)
            self.assertTrue(new[0].startswith(str(destination)))
            self.assertTrue(new[-1].startswith(str(destination)))
            self.assertNotEqual(old[0],new[0])
            self.assertNotEqual(old[-1],new[-1])
            self.assertTrue(v4.remove("demo-future-engine","1.0.0",root=destination))
            self.assertIsNone(v4.for_engine(result["engine_id"],root=destination))
            self.assertFalse(source.exists())

    def test_native_worker_launch_path_is_also_relocatable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            archive=fixture(folder/"package",kind="native")
            source=folder/"source-validation"
            destination=folder/"relocated-validation"
            with patch.object(v4,"sys_platform",return_value="windows-x64"):
                result=v4.install(archive,root=source)
            manifest,_=v4.for_engine(result["engine_id"],root=source)
            self.assertTrue(v4.ready(source,manifest))
            source.rename(destination)
            moved,_=v4.for_engine(result["engine_id"],root=destination)
            command=v4.worker_command(destination,moved)
            self.assertEqual(command[0],
                             str(destination/"models/universal/v4/tts/"
                                 "demo-future-engine/1.0.0/plugin/worker.exe"))
            self.assertEqual(command[1],"--model-dir")
            self.assertTrue(v4.remove("demo-future-engine","1.0.0",root=destination))


if __name__=="__main__":
    unittest.main()
