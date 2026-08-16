from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from dramaflow_qc.config import CONFIG_NAME, ProjectRules, VideoRules, load_config, write_default_config
from dramaflow_qc.hash_utils import sha256_file
from dramaflow_qc.inspectors.ffprobe import FFprobeError, parse_fraction, probe
from dramaflow_qc.inspectors.ffprobe import FFprobeUnavailable, MediaInfo
from dramaflow_qc.inspectors.loudness import FFmpegUnavailable, LoudnessError, integrated_lufs
from dramaflow_qc.inspectors.media import inspect_media
from dramaflow_qc.inspectors.project import inspect_filename, inspect_project
from dramaflow_qc.models import CheckResult, QCReport, Status
from dramaflow_qc.report import render_markdown


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


if __name__ == "__main__":
    unittest.main()
