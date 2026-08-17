from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class DecodeIntegrityUnavailable(RuntimeError):
    pass


class DecodeIntegrityError(RuntimeError):
    pass


_MAX_ERROR_DETAIL = 500


def _diagnostic_excerpt(output: str, path: Path) -> str:
    path_variants = {str(path), path.as_posix()}
    try:
        resolved = path.resolve()
        path_variants.update({str(resolved), resolved.as_posix()})
    except OSError:
        pass

    sanitized = output
    for variant in sorted(path_variants, key=len, reverse=True):
        if variant:
            sanitized = sanitized.replace(variant, "<media>")
    sanitized = sanitized.strip()
    if not sanitized:
        return ""
    if len(sanitized) <= _MAX_ERROR_DETAIL:
        return sanitized
    return "..." + sanitized[-_MAX_ERROR_DETAIL:]


def check_decode_integrity(path: Path) -> None:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise DecodeIntegrityUnavailable("ffmpeg was not found on PATH")

    command = [
        binary,
        "-nostdin",
        "-v", "error",
        "-xerror",
        "-i", str(path),
        "-map", "0:v?",
        "-map", "0:a?",
        "-f", "null",
        "-",
    ]
    completed = subprocess.run(command, capture_output=True, check=False)
    try:
        stdout = completed.stdout.decode("utf-8")
        stderr = completed.stderr.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecodeIntegrityError("ffmpeg decode output could not be decoded as UTF-8") from exc

    if completed.returncode != 0:
        output = _diagnostic_excerpt(stderr or stdout, path)
        detail = "FFmpeg full decode failed; media may be corrupt, incomplete, or otherwise undecodable."
        if output:
            detail = f"{detail} {output}"
        raise DecodeIntegrityError(detail)
