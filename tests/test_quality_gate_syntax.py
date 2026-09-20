"""Regression checks for compiler-only Python syntax errors in the quality gate."""

import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest


GATE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quality_gate.py"
SPEC = importlib.util.spec_from_file_location("quality_gate_syntax", GATE_PATH)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class QualityGateSyntaxTests(unittest.TestCase):
    def test_rejects_context_errors_that_ast_parsing_accepts(self):
        sources = (
            "return 1\n",
            "break\n",
            "continue\n",
            "yield 1\n",
            "await operation()\n",
            "nonlocal absent\n",
            "def operation():\n    nonlocal absent\n",
            "def operation(value, value):\n    pass\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.py"
            for source in sources:
                with self.subTest(source=source):
                    ast.parse(source)
                    path.write_text(source, encoding="utf-8")
                    errors = GATE.validate_files([path], set())
                    self.assertEqual(len(errors), 1)
                    self.assertIn(str(path), errors[0])
            self.assertFalse((Path(directory) / "__pycache__").exists())

    def test_accepts_valid_nested_and_async_contexts(self):
        source = (
            "def outer():\n"
            "    value = 1\n"
            "    def inner():\n"
            "        nonlocal value\n"
            "        value += 1\n"
            "        return value\n"
            "    return inner\n"
            "async def operation():\n"
            "    await another_operation()\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.py"
            path.write_text(source, encoding="utf-8")
            self.assertEqual(GATE.validate_files([path], set()), [])

    def test_validation_does_not_execute_source_or_write_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            path = Path(directory) / "side_effect.py"
            path.write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).touch()\n",
                encoding="utf-8",
            )
            self.assertEqual(GATE.validate_files([path], set()), [])
            self.assertFalse(marker.exists())
            self.assertFalse((Path(directory) / "__pycache__").exists())

    def test_changed_code_still_requires_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "implementation.py"
            path.write_text("def operation():\n    value = 1\n    return value\n", encoding="utf-8")
            errors = GATE.validate_files([path], {path})
            self.assertTrue(any("no module logger" in error for error in errors))
            self.assertTrue(any("has no log outcome" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
