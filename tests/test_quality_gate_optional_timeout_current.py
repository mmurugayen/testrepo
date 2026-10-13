"""Bounded optional syntax checks."""
import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("quality_gate_timeout_test", Path(__file__).resolve().parents[1] / "scripts" / "quality_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class OptionalSyntaxTimeoutTests(TestCase):
    def test_timeout_does_not_block_other_files(self):
        with patch.object(gate.shutil, "which", return_value="/usr/bin/fake"), patch.object(
            gate.subprocess, "run",
            side_effect=[subprocess.TimeoutExpired(["fake"], 15), SimpleNamespace(returncode=0, stdout="", stderr="")],
        ) as run:
            errors = gate.run_optional(["fake"], [Path("a"), Path("b")], "syntax")
        self.assertEqual(len(errors), 1)
        self.assertIn("timed out", errors[0])
        self.assertEqual(run.call_count, 2)
