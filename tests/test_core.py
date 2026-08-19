from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from pathlib import Path

from dramaflow_qc import __version__
from dramaflow_qc.config import CONFIG_NAME, ProjectRules, VideoRules, load_config, write_default_config
from dramaflow_qc.hash_utils import sha256_file
from dramaflow_qc.inspectors.decode import (
    DecodeIntegrityError,
    DecodeIntegrityUnavailable,
    check_decode_integrity,
)
from dramaflow_qc.inspectors.ffprobe import FFprobeError, parse_fraction, probe
from dramaflow_qc.inspectors.ffprobe import FFprobeUnavailable, MediaInfo
from dramaflow_qc.inspectors.loudness import FFmpegUnavailable, LoudnessError, integrated_lufs
from dramaflow_qc.inspectors.media import inspect_media
from dramaflow_qc.inspectors.project import inspect_filename, inspect_project
from dramaflow_qc.models import CheckResult, QCReport, Status
from dramaflow_qc.report import report_to_dict, render_json, render_markdown, write_json_report


class CoreTests(unittest.TestCase):
    @patch("dramaflow_qc.inspectors.media.probe", side_effect=FFprobeUnavailable("ffprobe was not found on PATH"))
    def test_missing_ffprobe_is_a_failed_check(self, probe_mock):
        results = inspect_media(Path("E01_MASTER.mp4"), VideoRules())
        self.assertEqual(results[0].name, "ffprobe")
        self.assertEqual(results[0].status, Status.FAIL)
        self.assertEqual(QCReport("demo", results).final_status, Status.FAIL)

    @patch("dramaflow_qc.inspectors.media.integrated_lufs", side_effect=FFmpegUnavailable("ffmpeg was not found on PATH"))
    @patch("dramaflow_qc.inspectors.media.probe")
    def test_missing_ffmpeg_fails_requested_loudness_check(self, probe_mock, lufs_mock):
        probe_mock.return_value = MediaInfo(1080, 1920, 24.0, "h264", "aac", 48000, 1.0)
        results = inspect_media(Path("E01_MASTER.mp4"), VideoRules())
        loudness = next(item for item in results if item.name == "Integrated loudness")
        self.assertEqual(loudness.status, Status.FAIL)
        self.assertEqual(QCReport("demo", results).final_status, Status.FAIL)

    @patch("dramaflow_qc.inspectors.media.integrated_lufs")
    @patch("dramaflow_qc.inspectors.media.probe")
    def test_no_loudness_does_not_require_ffmpeg(self, probe_mock, lufs_mock):
        probe_mock.return_value = MediaInfo(1080, 1920, 24.0, "h264", "aac", 48000, 1.0)
        results = inspect_media(Path("E01_MASTER.mp4"), VideoRules(), check_loudness=False)
        lufs_mock.assert_not_called()
        self.assertEqual(QCReport("demo", results).final_status, Status.PASS)

    @patch("dramaflow_qc.inspectors.decode.subprocess.run")
    @patch("dramaflow_qc.inspectors.decode.shutil.which", return_value="ffmpeg")
    def test_decode_integrity_passes_when_ffmpeg_decode_succeeds(self, which_mock, run_mock):
        completed = Mock(returncode=0, stdout=b"", stderr=b"")
        run_mock.return_value = completed
        media = Path("\u9879\u76ee with spaces/\u6210\u7247.mp4")

        check_decode_integrity(media)

        command = run_mock.call_args.args[0]
        self.assertEqual(command[:6], ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i"])
        self.assertEqual(command[6], str(media))
        self.assertIn("-nostdin", command)
        self.assertIn("-map", command)
        self.assertIn("0:v?", command)
        self.assertIn("0:a?", command)
        self.assertEqual(command[7:11], ["-map", "0:v?", "-map", "0:a?"])
        self.assertEqual(command[-3:], ["-f", "null", "-"])
        self.assertEqual(run_mock.call_args.kwargs, {"capture_output": True, "check": False})
        self.assertNotIn("shell", run_mock.call_args.kwargs)

    @patch("dramaflow_qc.inspectors.decode.shutil.which", return_value=None)
    def test_decode_integrity_missing_ffmpeg_fails(self, which_mock):
        with self.assertRaisesRegex(DecodeIntegrityUnavailable, "ffmpeg was not found on PATH"):
            check_decode_integrity(Path("E01_MASTER.mp4"))

    @patch("dramaflow_qc.inspectors.decode.subprocess.run")
    @patch("dramaflow_qc.inspectors.decode.shutil.which", return_value="ffmpeg")
    def test_decode_integrity_failure_is_controlled_and_sanitized(self, which_mock, run_mock):
        media = Path(r"C:\private\project\E01_MASTER.mp4")
        completed = Mock(
            returncode=1,
            stdout=b"",
            stderr=f"{media}: Invalid data found when processing input".encode("utf-8"),
        )
        run_mock.return_value = completed

        with self.assertRaisesRegex(DecodeIntegrityError, "otherwise undecodable"):
            check_decode_integrity(media)
        try:
            check_decode_integrity(media)
        except DecodeIntegrityError as exc:
            self.assertNotIn(str(media), str(exc))
            self.assertIn("<media>", str(exc))

    @patch("dramaflow_qc.inspectors.decode.subprocess.run")
    @patch("dramaflow_qc.inspectors.decode.shutil.which", return_value="ffmpeg")
    def test_decode_integrity_rejects_invalid_utf8_output(self, which_mock, run_mock):
        completed = Mock(returncode=1, stdout=b"", stderr=b"decode\xff")
        run_mock.return_value = completed
        with self.assertRaisesRegex(DecodeIntegrityError, "could not be decoded as UTF-8"):
            check_decode_integrity(Path("\u9879\u76ee/\u6210\u7247.mp4"))

    @patch("dramaflow_qc.inspectors.media.check_decode_integrity")
    @patch("dramaflow_qc.inspectors.media.probe")
    def test_decode_integrity_not_requested_does_not_call_ffmpeg(self, probe_mock, decode_mock):
        probe_mock.return_value = MediaInfo(1080, 1920, 24.0, "h264", "aac", 48000, 1.0)
        results = inspect_media(Path("E01_MASTER.mp4"), VideoRules(), check_loudness=False)
        decode_mock.assert_not_called()
        self.assertEqual(QCReport("demo", results).final_status, Status.PASS)

    @patch("dramaflow_qc.inspectors.media.check_decode_integrity")
    @patch("dramaflow_qc.inspectors.media.probe")
    def test_decode_integrity_requested_adds_pass_result(self, probe_mock, decode_mock):
        probe_mock.return_value = MediaInfo(1080, 1920, 24.0, "h264", "aac", 48000, 1.0)
        results = inspect_media(
            Path("E01_MASTER.mp4"),
            VideoRules(),
            check_loudness=False,
            check_decode=True,
        )
        item = next(result for result in results if result.name == "Decode integrity")
        self.assertEqual(item.status, Status.PASS)
        self.assertEqual(QCReport("demo", results).final_status, Status.PASS)

    @patch(
        "dramaflow_qc.inspectors.media.check_decode_integrity",
        side_effect=DecodeIntegrityError(
            "FFmpeg full decode failed; media may be corrupt, incomplete, or otherwise undecodable."
        ),
    )
    @patch("dramaflow_qc.inspectors.media.probe")
    def test_decode_integrity_requested_adds_fail_result(self, probe_mock, decode_mock):
        probe_mock.return_value = MediaInfo(1080, 1920, 24.0, "h264", "aac", 48000, 1.0)
        results = inspect_media(
            Path("E01_MASTER.mp4"),
            VideoRules(),
            check_loudness=False,
            check_decode=True,
        )
        item = next(result for result in results if result.name == "Decode integrity")
        self.assertEqual(item.status, Status.FAIL)
        self.assertEqual(QCReport("demo", results).final_status, Status.FAIL)

    def test_parse_fraction(self):
        self.assertEqual(parse_fraction("24/1"), 24.0)
        self.assertAlmostEqual(parse_fraction("24000/1001"), 23.9760239, places=5)
        self.assertIsNone(parse_fraction("0/0"))

    def test_probe_uses_utf8_for_non_ascii_paths(self):
        payload = json.dumps({
            "streams": [{
                "codec_type": "video",
                "width": 1080,
                "height": 1920,
                "avg_frame_rate": "24/1",
                "codec_name": "h264",
            }],
            "format": {"duration": "1.0"},
        })
        completed = Mock(returncode=0, stdout=payload.encode("utf-8"), stderr=b"")
        with patch("dramaflow_qc.inspectors.ffprobe.shutil.which", return_value="ffprobe"), \
             patch("dramaflow_qc.inspectors.ffprobe.subprocess.run", return_value=completed) as run:
            info = probe(Path("项目/成片.mp4"))
        self.assertEqual(info.width, 1080)
        self.assertEqual(run.call_args.kwargs, {"capture_output": True, "check": False})

    def test_loudness_uses_utf8_for_non_ascii_paths(self):
        completed = Mock(returncode=0, stdout=b"", stderr="路径 项目/成片.mp4\n  I:         -16.0 LUFS\n".encode("utf-8"))
        with patch("dramaflow_qc.inspectors.loudness.shutil.which", return_value="ffmpeg"), \
             patch("dramaflow_qc.inspectors.loudness.subprocess.run", return_value=completed) as run:
            value = integrated_lufs(Path("项目/成片.mp4"))
        self.assertEqual(value, -16.0)
        self.assertEqual(run.call_args.kwargs, {"capture_output": True, "check": False})

    def test_probe_rejects_invalid_utf8_output(self):
        completed = Mock(returncode=0, stdout=b"{\xff", stderr=b"")
        with patch("dramaflow_qc.inspectors.ffprobe.shutil.which", return_value="ffprobe"), \
             patch("dramaflow_qc.inspectors.ffprobe.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(FFprobeError, "could not be decoded as UTF-8"):
                probe(Path("项目/成片.mp4"))

    def test_loudness_rejects_invalid_utf8_output(self):
        completed = Mock(returncode=0, stdout=b"", stderr=b"ffmpeg\xff")
        with patch("dramaflow_qc.inspectors.loudness.shutil.which", return_value="ffmpeg"), \
             patch("dramaflow_qc.inspectors.loudness.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(LoudnessError, "could not be decoded as UTF-8"):
                integrated_lufs(Path("项目/成片.mp4"))

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

    def test_report_to_dict_serializes_schema_summary_order_and_unicode(self):
        report = QCReport(
            "D:/项目/成片.mp4",
            [
                CheckResult("Resolution", Status.PASS, "1080x1920", "1080x1920"),
                CheckResult("Filename rule", Status.WARNING, "成片.mp4", "ASCII", "人工复核"),
                CheckResult("Frame rate", Status.FAIL, "30.000", "24"),
                CheckResult("Duration", Status.INFO, "93.205s"),
            ],
            sha256=None,
        )

        data = report_to_dict(report, generated_at="2026-08-19T12:00:00+00:00")

        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["tool_version"], __version__)
        self.assertEqual(data["generated_at"], "2026-08-19T12:00:00+00:00")
        self.assertEqual(data["target"], "D:/项目/成片.mp4")
        self.assertEqual(data["final_status"], "FAIL")
        self.assertIsNone(data["sha256"])
        self.assertEqual(data["summary"], {"total": 4, "pass": 1, "warning": 1, "fail": 1, "info": 1})
        self.assertEqual([item["name"] for item in data["checks"]], [
            "Resolution",
            "Filename rule",
            "Frame rate",
            "Duration",
        ])
        self.assertEqual(data["checks"][1], {
            "name": "Filename rule",
            "status": "WARNING",
            "actual": "成片.mp4",
            "expected": "ASCII",
            "detail": "人工复核",
        })

    def test_report_to_dict_final_status_values_use_qcreport(self):
        cases = [
            ("PASS", [CheckResult("Resolution", Status.PASS)]),
            ("WARNING", [CheckResult("Filename rule", Status.WARNING)]),
            ("FAIL", [CheckResult("Frame rate", Status.FAIL)]),
        ]
        for expected, results in cases:
            with self.subTest(expected=expected):
                self.assertEqual(report_to_dict(QCReport("demo", results))["final_status"], expected)

    def test_render_json_parses_and_preserves_unicode(self):
        report = QCReport("D:/项目/成片.mp4", [CheckResult("Filename rule", Status.FAIL, "成片.mp4")], sha256="ABC123")

        text = render_json(report, generated_at=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc))
        data = json.loads(text)

        self.assertTrue(text.endswith("\n"))
        self.assertIn("成片.mp4", text)
        self.assertEqual(data["sha256"], "ABC123")
        self.assertEqual(data["checks"][0]["status"], "FAIL")

    def test_report_to_dict_rejects_naive_generated_at(self):
        report = QCReport("demo", [CheckResult("Resolution", Status.PASS)])

        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            report_to_dict(report, generated_at=datetime(2026, 8, 19, 12, 0))

    def test_write_json_report_uses_utf8_and_newline(self):
        report = QCReport("D:/项目/成片.mp4", [CheckResult("Filename rule", Status.PASS, "成片.mp4")])
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "qc.json"
            write_json_report(report, destination)
            raw = destination.read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            text = raw.decode("utf-8")
            self.assertIn("成片.mp4", text)
            self.assertEqual(json.loads(text)["summary"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
