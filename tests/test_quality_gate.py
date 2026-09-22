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


class LoggingContractRegressionTests(unittest.TestCase):
    def errors(self, source):
        return GATE.logging_errors(Path("implementation.py"), ast.parse(source))

    def test_placeholder_assignments_do_not_satisfy_module_logger(self):
        operation = "def operation():\n    logger.info('completed')\n    return 1\n"
        for assignment in (
            "logger = None", "logger = 0", "logger = 'fake'",
            "logger: object", "logger = object()",
            "logger = fake.getLogger(__name__)",
            "import logging\nlogger = logging.getLogger(__name__)\nlogger = None",
        ):
            with self.subTest(assignment=assignment):
                self.assertTrue(any("no module logger" in error for error in
                                    self.errors(assignment + "\n" + operation)))

    def test_imported_logger_factories_and_aliases_are_supported(self):
        operation = "def operation():\n    logger.info('completed')\n    return 1\n"
        for assignment in (
            "import logging\nlogger = logging.getLogger(__name__)",
            "import logging as diag\nlogger = diag.getLogger(__name__)",
            "from logging import getLogger\nlogger = getLogger(__name__)",
            "from logging import getLogger as get_logger\nlogger = get_logger(__name__)",
            "import logging\nlogger: logging.Logger = logging.getLogger(__name__)",
        ):
            with self.subTest(assignment=assignment):
                self.assertEqual(self.errors(assignment + "\n" + operation), [])

    def test_single_statement_operations_require_outcome_logging(self):
        prefix = "import logging\nlogger = logging.getLogger(__name__)\n"
        for operation in (
            "def save():\n    database.commit()\n",
            "def save():\n    return database.commit()\n",
            "async def save():\n    await database.commit()\n",
            "def save():\n    if ready:\n        database.commit()\n",
            "def save():\n    for item in items:\n        database.write(item)\n",
            "def save(self, value):\n    self.value = value\n",
            "def save(self, value):\n    self.value: object = value\n",
            "def save(self, key, value):\n    self.values[key] = value\n",
            "def save(self, value):\n    self.value, local = value, 1\n",
        ):
            with self.subTest(operation=operation):
                self.assertTrue(any("has no log outcome" in error for error in
                                    self.errors(prefix + operation)))

    def test_trivial_pure_helpers_do_not_require_noisy_logging(self):
        for operation in (
            "def value():\n    return 1\n",
            "def value():\n    return self.value\n",
            "def value():\n    return x + 1\n",
            "def value():\n    'Pure getter.'\n    return self.value\n",
        ):
            with self.subTest(operation=operation):
                self.assertEqual(self.errors(operation), [])

    def test_single_statement_real_emission_satisfies_logging(self):
        self.assertEqual(self.errors(
            "import logging\nlogger = logging.getLogger(__name__)\n"
            "def report():\n    logger.info('completed')\n"
        ), [])
