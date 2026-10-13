"""Regression coverage for NUL-delimited changed paths."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("quality_gate_under_test", Path(__file__).resolve().parents[1] / "scripts" / "quality_gate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ChangedPathsTests(TestCase):
    def test_newline_and_tab_paths(self):
        paths = [Path("src/new\nline.py"), Path("src/with\ttab.py")]
        payload = b"src/new\nline.py\0src/with\ttab.py\0"
        with patch.object(module.subprocess, "run", return_value=SimpleNamespace(stdout=payload)) as run:
            self.assertEqual(module.changed_files("main", paths), set(paths))
        self.assertIn("-z", run.call_args.args[0])
