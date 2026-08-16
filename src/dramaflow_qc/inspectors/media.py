from __future__ import annotations

from pathlib import Path

from dramaflow_qc.config import VideoRules
from dramaflow_qc.inspectors.decode import (
    DecodeIntegrityError,
    DecodeIntegrityUnavailable,
    check_decode_integrity,
)
from dramaflow_qc.inspectors.ffprobe import FFprobeError, FFprobeUnavailable, probe
from dramaflow_qc.inspectors.loudness import FFmpegUnavailable, LoudnessError, integrated_lufs
from dramaflow_qc.models import CheckResult, Status


def inspect_media(
    path: Path,
    rules: VideoRules,
    check_loudness: bool = True,
    check_decode: bool = False,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        info = probe(path)
    except FFprobeUnavailable as exc:
        return [CheckResult("ffprobe", Status.FAIL, detail=str(exc))]
    except FFprobeError as exc:
        return [CheckResult("ffprobe", Status.FAIL, detail=str(exc))]

    results.append(CheckResult(
        "Resolution",
        Status.PASS if (info.width, info.height) == (rules.width, rules.height) else Status.FAIL,
        actual=f"{info.width}x{info.height}",
        expected=f"{rules.width}x{rules.height}",
    ))

    fps_ok = info.fps is not None and abs(info.fps - rules.fps) < 0.02
    results.append(CheckResult(
        "Frame rate",
        Status.PASS if fps_ok else Status.FAIL,
        actual=f"{info.fps:.3f}" if info.fps is not None else "missing",
        expected=f"{rules.fps:g}",
    ))

    results.append(CheckResult(
        "Video codec",
        Status.PASS if info.video_codec == rules.video_codec else Status.FAIL,
        actual=info.video_codec or "missing",
        expected=rules.video_codec,
    ))

    results.append(CheckResult(
        "Audio sample rate",
        Status.PASS if info.audio_sample_rate == rules.audio_sample_rate else Status.FAIL,
        actual=str(info.audio_sample_rate or "missing"),
        expected=str(rules.audio_sample_rate),
    ))

    if info.duration is not None:
        results.append(CheckResult("Duration", Status.INFO, actual=f"{info.duration:.3f}s"))

    if check_loudness:
        try:
            lufs = integrated_lufs(path)
            delta = abs(lufs - rules.target_lufs)
            results.append(CheckResult(
                "Integrated loudness",
                Status.PASS if delta <= rules.lufs_tolerance else Status.FAIL,
                actual=f"{lufs:.1f} LUFS",
                expected=f"{rules.target_lufs:.1f} ± {rules.lufs_tolerance:.1f} LUFS",
            ))
        except FFmpegUnavailable as exc:
            results.append(CheckResult("Integrated loudness", Status.FAIL, detail=str(exc)))
        except LoudnessError as exc:
            results.append(CheckResult("Integrated loudness", Status.WARNING, detail=str(exc)))

    if check_decode:
        try:
            check_decode_integrity(path)
            results.append(CheckResult(
                "Decode integrity",
                Status.PASS,
                detail="Full FFmpeg decode completed without fatal errors.",
            ))
        except DecodeIntegrityUnavailable as exc:
            results.append(CheckResult("Decode integrity", Status.FAIL, detail=str(exc)))
        except DecodeIntegrityError as exc:
            results.append(CheckResult("Decode integrity", Status.FAIL, detail=str(exc)))

    return results
