from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dramaflow_qc.cli import main
from dramaflow_qc.models import CheckResult, Status


class CLITests(unittest.TestCase):
    def test_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["init", tmp]), 0)
            self.assertTrue((Path(tmp) / ".dramaflow-qc.json").exists())

    def test_project_fail_when_required_path_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["project", tmp]), 2)

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_writes_report(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [CheckResult("Resolution", Status.PASS, "1080x1920", "1080x1920")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            media.write_bytes(b"not-real-video")
            code = main(["check", str(media), "--no-loudness"])
            self.assertEqual(code, 0)
            self.assertTrue((root / "QC_REPORTS" / "E01_MASTER_QC.md").exists())


if __name__ == "__main__":
    unittest.main()
