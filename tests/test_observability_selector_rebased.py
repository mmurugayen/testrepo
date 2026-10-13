"""Regression: non-string selectors must fail before membership lookup."""
import importlib.util
from pathlib import Path
from unittest import TestCase

spec = importlib.util.spec_from_file_location("observability_selector_under_test", Path(__file__).resolve().parents[1] / "scripts" / "gysam_observability.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SelectorTypeTests(TestCase):
    def test_unhashable_and_numeric_selectors(self):
        reader = module.LogReader([])
        for selector in ([], {}, 1, True, set()):
            with self.subTest(selector=selector):
                with self.assertRaisesRegex(ValueError, "invalid_selector"):
                    reader.read(selector=selector, value="example")
