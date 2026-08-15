# DramaFlow QC

DramaFlow QC is a local-first command-line quality-control tool for AI-generated video, short-drama, and creator production pipelines.

It turns repeatable delivery requirements into machine-checkable rules and produces a human-readable Markdown report with a clear `PASS`, `WARNING`, or `FAIL` result.

## Project status

`0.1.0-alpha` — usable locally, API and configuration may still change before `1.0`.

## V0.1 scope

- Resolution check
- Frame-rate check
- Video codec check
- Audio sample-rate check
- EBU R128 integrated loudness check via FFmpeg
- SHA256 file integrity hash
- Configurable filename rule
- Configurable required project paths
- Markdown QC report

No cloud account, database, or API key is required.

## Requirements

- Python 3.10+
- FFmpeg + FFprobe on `PATH` for media inspection

## Install for development

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
```

## Quick start

Create the project config:

```bash
dramaflow-qc init
```

Check a video:

```bash
dramaflow-qc check E01_MASTER_9x16.mp4
```

The default report is written to:

```text
QC_REPORTS/E01_MASTER_9x16_QC.md
```

Check project-level required paths:

```bash
dramaflow-qc project .
```

## Default rules

The generated `.dramaflow-qc.json` starts with creator-friendly vertical-video defaults:

```json
{
  "video": {
    "width": 1080,
    "height": 1920,
    "fps": 24.0,
    "video_codec": "h264",
    "audio_sample_rate": 48000,
    "target_lufs": -16.0,
    "lufs_tolerance": 1.5
  },
  "project": {
    "required_paths": ["QC_REPORTS"],
    "filename_regex": "^[A-Za-z0-9][A-Za-z0-9._-]*\\.(mp4|mov|mkv)$"
  }
}
```

Edit these values to match your own pipeline.

## Exit codes

- `0`: PASS or WARNING
- `2`: FAIL / invalid target

This makes DramaFlow QC suitable for local automation and CI.

## Roadmap

- Full decode integrity check
- Subtitle/SRT event checks
- JSON report output
- Batch folder scanning
- GitHub Actions example
- Rule profiles for 9:16, 16:9, and platform delivery presets

## License

MIT
