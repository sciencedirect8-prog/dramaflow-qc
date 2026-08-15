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
    # FFmpeg diagnostics are UTF-8; do not decode them with the Windows locale.
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = completed.stderr
    matches = _INTEGRATED_RE.findall(output)
    if not matches:
        raise LoudnessError("Could not parse integrated loudness from ffmpeg ebur128 output")
    return float(matches[-1])
