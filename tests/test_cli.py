from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
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
            self.assertFalse((root / "QC_REPORTS" / "E01_MASTER_QC.json").exists())
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
                detail="FFmpeg full decode failed; media may be corrupt, incomplete, or otherwise undecodable.",
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

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_json_report_writes_markdown_and_json_sidecar(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [CheckResult("Resolution", Status.PASS, "1080x1920", "1080x1920")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            json_report = root / "QC_REPORTS" / "E01_MASTER_QC.json"
            media.write_bytes(b"not-real-video")
            code = main(["check", str(media), "--no-loudness", "--json-report", str(json_report)])

            self.assertEqual(code, 0)
            self.assertTrue((root / "QC_REPORTS" / "E01_MASTER_QC.md").exists())
            self.assertTrue(json_report.exists())
            data = json.loads(json_report.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "1.0")
            self.assertEqual(data["sha256"], "ABC123")
            self.assertEqual(data["final_status"], "PASS")
            self.assertEqual(data["summary"]["total"], len(data["checks"]))

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_custom_markdown_and_json_destinations_write_both(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [CheckResult("Resolution", Status.PASS, "1080x1920", "1080x1920")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            markdown_report = root / "custom.md"
            json_report = root / "custom.json"
            media.write_bytes(b"not-real-video")
            code = main([
                "check",
                str(media),
                "--no-loudness",
                "--report",
                str(markdown_report),
                "--json-report",
                str(json_report),
            ])

            self.assertEqual(code, 0)
            self.assertTrue(markdown_report.exists())
            self.assertTrue(json_report.exists())
            self.assertIn("# DramaFlow QC Report", markdown_report.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(json_report.read_text(encoding="utf-8"))["final_status"], "PASS")

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_json_report_fail_qc_preserves_exit_2(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [CheckResult("Frame rate", Status.FAIL, "30.000", "24")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            json_report = root / "qc.json"
            media.write_bytes(b"not-real-video")
            code = main(["check", str(media), "--no-loudness", "--json-report", str(json_report)])

            self.assertEqual(code, 2)
            data = json.loads(json_report.read_text(encoding="utf-8"))
            self.assertEqual(data["final_status"], "FAIL")

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_json_report_warning_qc_preserves_exit_0(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [CheckResult("Advisory", Status.WARNING, detail="Review manually")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            json_report = root / "qc.json"
            media.write_bytes(b"not-real-video")
            code = main(["check", str(media), "--no-loudness", "--json-report", str(json_report)])

            self.assertEqual(code, 0)
            data = json.loads(json_report.read_text(encoding="utf-8"))
            self.assertEqual(data["final_status"], "WARNING")

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_json_report_includes_decode_integrity_result(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [
            CheckResult(
                "Decode integrity",
                Status.PASS,
                detail="Full FFmpeg decode completed without fatal errors.",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            json_report = root / "qc.json"
            media.write_bytes(b"not-real-video")
            code = main([
                "check",
                str(media),
                "--no-loudness",
                "--decode-integrity",
                "--json-report",
                str(json_report),
            ])

            self.assertEqual(code, 0)
            self.assertTrue(inspect_mock.call_args.kwargs["check_decode"])
            data = json.loads(json_report.read_text(encoding="utf-8"))
            self.assertTrue(any(item["name"] == "Decode integrity" for item in data["checks"]))

    @patch("dramaflow_qc.cli.inspect_media")
    @patch("dramaflow_qc.cli.sha256_file")
    def test_check_json_report_write_failure_is_controlled(self, hash_mock, inspect_mock):
        hash_mock.return_value = "ABC123"
        inspect_mock.return_value = [CheckResult("Resolution", Status.PASS, "1080x1920", "1080x1920")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "E01_MASTER.mp4"
            json_destination = root / "existing-directory"
            json_destination.mkdir()
            media.write_bytes(b"not-real-video")
            stderr = StringIO()

            with redirect_stderr(stderr):
                code = main(["check", str(media), "--no-loudness", "--json-report", str(json_destination)])

            self.assertEqual(code, 2)
            self.assertTrue((root / "QC_REPORTS" / "E01_MASTER_QC.md").exists())
            self.assertIn("ERROR: could not write JSON report:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

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
