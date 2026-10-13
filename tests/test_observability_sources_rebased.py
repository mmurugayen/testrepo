"""Log source validation and configuration snapshot regression coverage."""
import importlib.util
from pathlib import Path
from unittest import TestCase

spec = importlib.util.spec_from_file_location("observability_sources_under_test", Path(__file__).resolve().parents[1] / "scripts" / "gysam_observability.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LogSourceSnapshotTests(TestCase):
    def test_non_mapping_sources_rejected(self):
        for value in (None, "path", 123, []):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid_log_source"):
                    module.LogReader([value])

    def test_source_mapping_copied(self):
        source = {"id": "audit", "path": "/tmp/original"}
        reader = module.LogReader([source])
        source["path"] = "/tmp/changed"
        self.assertEqual(reader.sources[0]["path"], "/tmp/original")
