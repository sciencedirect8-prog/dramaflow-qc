from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class FFmpegUnavailable(RuntimeError):
    pass


class LoudnessError(RuntimeError):
    pass


_INTEGRATED_RE = re.compile(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS\s*$", re.MULTILINE)


def integrated_lufs(path: Path) -> float:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise FFmpegUnavailable("ffmpeg was not found on PATH")
    command = [
        binary,
        "-hide_banner",
        "-nostats",
        "-i", str(path),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null",
        "-",
    ]
    completed = subprocess.run(command, capture_output=True, check=False)
    try:
        output = completed.stderr.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LoudnessError("ffmpeg output could not be decoded as UTF-8") from exc
    matches = _INTEGRATED_RE.findall(output)
    if not matches:
        raise LoudnessError("Could not parse integrated loudness from ffmpeg ebur128 output")
    return float(matches[-1])
