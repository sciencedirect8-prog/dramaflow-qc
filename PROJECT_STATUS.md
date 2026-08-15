# DramaFlow QC — V0.1 Development Status

Status: MVP IMPLEMENTED / LOCAL TEST PASS
Date: 2026-08-15

## Implemented

- `dramaflow-qc init`
- `dramaflow-qc check <video>`
- `dramaflow-qc project <directory>`
- FFprobe media metadata inspection
- Resolution / FPS / codec / audio sample-rate checks
- FFmpeg EBU R128 integrated loudness check
- SHA256 calculation
- Configurable filename regex
- Configurable required project paths
- Markdown QC report
- CI-friendly exit codes
- GitHub Actions CI definition
- Unit tests
- PASS and FAIL real-media integration validation

## Validation

- Unit tests: 10/10 PASS
- Python compileall: PASS
- Package editable install: PASS (with local no-build-isolation in restricted environment)
- CLI entry point: PASS
- FFmpeg integration: PASS
- FFprobe integration: PASS
- Known-low-loudness media correctly returns FAIL
- Conforming media correctly returns PASS

## Publication

GitHub publication status is tracked by the repository hosting service and is separate from this local validation snapshot.
