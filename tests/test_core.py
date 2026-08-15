from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dramaflow_qc.config import CONFIG_NAME, ProjectRules, load_config, write_default_config
from dramaflow_qc.hash_utils import sha256_file
from dramaflow_qc.inspectors.ffprobe import parse_fraction
from dramaflow_qc.inspectors.project import inspect_filename, inspect_project
from dramaflow_qc.models import CheckResult, QCReport, Status
from dramaflow_qc.report import render_markdown


class CoreTests(unittest.TestCase):
    def test_parse_fraction(self):
        self.assertEqual(parse_fraction("24/1"), 24.0)
        self.assertAlmostEqual(parse_fraction("24000/1001"), 23.9760239, places=5)
        self.assertIsNone(parse_fraction("0/0"))

    def test_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.bin"
            path.write_bytes(b"abc")
            self.assertEqual(
                sha256_file(path),
                "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD",
            )

    def test_default_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_default_config(root)
            self.assertEqual(path.name, CONFIG_NAME)
            cfg = load_config(root)
            self.assertEqual(cfg.video.width, 1080)
            self.assertEqual(cfg.video.height, 1920)
            self.assertEqual(cfg.video.audio_sample_rate, 48000)

    def test_load_custom_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = {
                "video": {"width": 1920, "height": 1080},
                "project": {"required_paths": ["out"], "filename_regex": ".*\\.mp4"},
            }
            (root / CONFIG_NAME).write_text(json.dumps(data), encoding="utf-8")
            cfg = load_config(root)
            self.assertEqual(cfg.video.width, 1920)
            self.assertEqual(cfg.video.height, 1080)
            self.assertEqual(cfg.video.fps, 24.0)

    def test_project_required_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "QC_REPORTS").mkdir()
            results = inspect_project(root, ProjectRules(required_paths=["QC_REPORTS", "missing"]))
            self.assertEqual(results[0].status, Status.PASS)
            self.assertEqual(results[1].status, Status.FAIL)

    def test_filename_rule(self):
        rules = ProjectRules()
        self.assertEqual(inspect_filename(Path("E01_MASTER_9x16.mp4"), rules).status, Status.PASS)
        self.assertEqual(inspect_filename(Path("bad name.mp4"), rules).status, Status.FAIL)

    def test_report_final_status(self):
        report = QCReport("demo", [CheckResult("x", Status.PASS), CheckResult("y", Status.WARNING)])
        self.assertEqual(report.final_status, Status.WARNING)
        text = render_markdown(report)
        self.assertIn("**WARNING**", text)


if __name__ == "__main__":
    unittest.main()
