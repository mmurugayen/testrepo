"""Offline tests for bounded optional syntax checks."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

script = Path(__file__).resolve().parents[1] / "scripts" / "quality_gate.py"
spec = importlib.util.spec_from_file_location("quality_gate_test_bounds", script)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class OptionalChecksTests(unittest.TestCase):
    def test_timeout(self):
        with patch.object(gate.shutil, "which", return_value="/bin/bash"), patch.object(
            gate.subprocess, "run", side_effect=subprocess.TimeoutExpired(["bash"], 15)
        ) as call:
            errors = gate.run_optional(["bash", "-n"], [Path("check.sh")], "bash syntax")
        self.assertIn("timed out", errors[0])
        self.assertEqual(call.call_args.kwargs["timeout"], 15)

    def test_spawn_error_is_redacted(self):
        with patch.object(gate.shutil, "which", return_value="/bin/bash"), patch.object(
            gate.subprocess, "run", side_effect=OSError("private credentials")
        ):
            errors = gate.run_optional(["bash", "-n"], [Path("check.sh")], "bash syntax")
        self.assertIn("unavailable", errors[0])
        self.assertNotIn("private credentials", errors[0])

    def test_output_is_truncated(self):
        result = subprocess.CompletedProcess([], 1, "", "x" * 10000)
        with patch.object(gate.shutil, "which", return_value="/bin/bash"), patch.object(
            gate.subprocess, "run", return_value=result
        ):
            errors = gate.run_optional(["bash", "-n"], [Path("check.sh")], "bash syntax")
        self.assertLess(len(errors[0]), 2200)

    def test_terraform_formatter_timeout(self):
        with patch.object(gate.shutil, "which", side_effect=lambda name: "/usr/bin/terraform" if name == "terraform" else None), patch.object(
            gate.subprocess, "run", side_effect=subprocess.TimeoutExpired(["terraform"], 120)
        ) as call:
            errors = gate.validate_terraform([Path("main.tf")])
        self.assertIn("timed out", errors[0])
        self.assertEqual(call.call_args.kwargs["timeout"], 120)



if __name__ == "__main__":
    unittest.main()
