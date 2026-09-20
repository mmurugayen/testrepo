"""Portable checks of syntax rejection and conservative logging evidence."""
import ast
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "quality_gate", Path(__file__).resolve().parents[1] / "scripts/quality_gate.py"
)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class QualityGateTests(unittest.TestCase):
    def test_emission_methods_are_recognized(self):
        for method in GATE.LOG_METHODS:
            with self.subTest(method=method):
                node = ast.parse(
                    f"def operation():\n    logger.{method}('safe_event')\n"
                ).body[0]
                self.assertTrue(GATE.has_log_call(node))

    def test_queries_and_uninvoked_nested_scopes_are_not_outcomes(self):
        for source in ("def f():\n    logger.isEnabledFor(20)\n", "def f():\n    def inner():\n        logger.info('safe')\n", "def f():\n    callback = lambda: logger.info('safe')\n", "def f():\n    class Inner:\n        def emit(self):\n            logger.info('safe')\n"):
            with self.subTest(source=source):
                self.assertFalse(GATE.has_log_call(ast.parse(source).body[0]))

    def test_missing_optional_runtime_reports_unverified(self):
        stream = io.StringIO()
        with patch.object(GATE.shutil, "which", return_value=None), redirect_stderr(stream):
            self.assertEqual(GATE.run_optional(["node", "--check"], [Path("app.js")], "JavaScript syntax"), [])
            self.assertEqual(GATE.validate_terraform([Path("main.tf")]), [])
        self.assertEqual(stream.getvalue().count("SKIP:"), 2)
        self.assertIn("unverified", stream.getvalue())

    def test_no_relevant_files_do_not_report_skip(self):
        stream = io.StringIO()
        with patch.object(GATE.shutil, "which", return_value=None), redirect_stderr(stream):
            self.assertEqual(GATE.run_optional(["node", "--check"], [], "JavaScript syntax"), [])
            self.assertEqual(GATE.validate_terraform([]), [])
        self.assertEqual(stream.getvalue(), "")
