from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dramaflow_qc.cli import _exit_code, main
from dramaflow_qc.inspectors.ffprobe import FFprobeUnavailable
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
            inspect_mock.assert_called_once()
            self.assertFalse(inspect_mock.call_args.kwargs["check_decode"])

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_decode_integrity_failure_writes_report_and_exits_2(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [
            CheckResult(
                "Decode integrity",
                Status.FAIL,
                detail="FFmpeg full decode failed: corrupt or incomplete media stream detected.",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            media.write_bytes(b"not-real-video")
            code = main(["check", str(media), "--no-loudness", "--decode-integrity"])
            report = root / "QC_REPORTS" / "E01_MASTER_QC.md"
            self.assertEqual(code, 2)
            self.assertTrue(report.exists())
            self.assertIn("| FAIL | Decode integrity |", report.read_text(encoding="utf-8"))
            self.assertTrue(inspect_mock.call_args.kwargs["check_decode"])

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_decode_integrity_success_exits_0(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [
            CheckResult("Resolution", Status.PASS, "1080x1920", "1080x1920"),
            CheckResult(
                "Decode integrity",
                Status.PASS,
                detail="Full FFmpeg decode completed without fatal errors.",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            media.write_bytes(b"not-real-video")
            code = main(["check", str(media), "--no-loudness", "--decode-integrity"])
            self.assertEqual(code, 0)
            self.assertTrue(inspect_mock.call_args.kwargs["check_decode"])

    @patch("dramaflow_qc.inspectors.media.probe", side_effect=FFprobeUnavailable("ffprobe was not found on PATH"))
    def test_check_fails_and_writes_report_when_ffprobe_is_missing(self, probe_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            media.write_bytes(b"not-real-video")
            code = main(["check", str(media), "--no-loudness"])
            report = root / "QC_REPORTS" / "E01_MASTER_QC.md"
            self.assertEqual(code, 2)
            self.assertTrue(report.exists())
            self.assertIn("| FAIL | ffprobe |", report.read_text(encoding="utf-8"))

    def test_non_fatal_warning_still_exits_successfully(self):
        self.assertEqual(_exit_code(Status.WARNING), 0)


if __name__ == "__main__":
    unittest.main()
