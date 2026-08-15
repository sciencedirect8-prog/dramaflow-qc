# Architecture

DramaFlow QC intentionally separates four concerns:

1. **Configuration** — project rules loaded from `.dramaflow-qc.json`.
2. **Inspectors** — small validators for media and project structure.
3. **Result model** — normalized `PASS`, `WARNING`, `FAIL`, and `INFO` results.
4. **Reporting/CLI** — human-readable Markdown output and automation-friendly exit codes.

The core package does not require an online service. FFmpeg/FFprobe are invoked as local subprocesses, making the tool suitable for creator workstations and CI runners.

Future validators should avoid modifying source media. QC should be read-only by default.
