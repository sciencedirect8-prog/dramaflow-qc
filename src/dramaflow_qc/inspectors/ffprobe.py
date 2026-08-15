from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FFprobeUnavailable(RuntimeError):
    pass


class FFprobeError(RuntimeError):
    pass


@dataclass(slots=True)
class MediaInfo:
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    duration: float | None = None


def parse_fraction(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            den = float(denominator)
            return float(numerator) / den if den else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def probe(path: Path) -> MediaInfo:
    binary = shutil.which("ffprobe")
    if not binary:
        raise FFprobeUnavailable("ffprobe was not found on PATH")

    command = [
        binary,
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise FFprobeError(completed.stderr.strip() or "ffprobe failed")

    data = json.loads(completed.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration_raw = data.get("format", {}).get("duration")

    return MediaInfo(
        width=video.get("width"),
        height=video.get("height"),
        fps=parse_fraction(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        video_codec=video.get("codec_name"),
        audio_codec=audio.get("codec_name"),
        audio_sample_rate=int(audio["sample_rate"]) if audio.get("sample_rate") else None,
        duration=float(duration_raw) if duration_raw not in {None, "N/A"} else None,
    )
