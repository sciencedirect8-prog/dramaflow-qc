# Changelog

## 0.1.1 - 2026-08-16

Maintenance alpha release.

- Fixed Windows Unicode / non-ASCII media paths causing FFprobe subprocess decoding failures.
- FFprobe and FFmpeg subprocess output is now captured as bytes and decoded explicitly as strict UTF-8.
- Invalid external-tool UTF-8 output now raises clear `FFprobeError` / `LoudnessError` instead of exposing raw `UnicodeDecodeError`.
- Added byte-level Unicode decoding regression tests.
- Added focused Windows Python 3.14 GitHub Actions coverage.

## 0.1.0 - 2026-08-15

Initial alpha release.

- Media metadata inspection through FFprobe.
- Resolution, frame rate, codec, and audio sample-rate rules.
- EBU R128 integrated loudness analysis through FFmpeg.
- SHA256 integrity hashing.
- Configurable filename and project-path rules.
- Markdown QC reports and CI-friendly exit codes.
