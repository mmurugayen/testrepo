"""Regression for non-UTF8 filenames from Git."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("quality_gate_tracked_paths", Path(__file__).resolve().parents[1] / "scripts" / "quality_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class TrackedPathEncodingTests(TestCase):
    def test_non_utf8_git_path(self):
        raw = b"src/nonutf8_\xff.py"
        with patch.object(gate.subprocess, "run", return_value=SimpleNamespace(stdout=raw + b"\0")):
            self.assertIn(Path(os.fsdecode(raw)), gate.tracked_files())
