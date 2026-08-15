from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dramaflow_qc.models import QCReport


def render_markdown(report: QCReport) -> str:
    lines = [
        "# DramaFlow QC Report",
        "",
        f"- Target: `{report.target}`",
        f"- Generated: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Final status: **{report.final_status.value}**",
    ]
    if report.sha256:
        lines.append(f"- SHA256: `{report.sha256}`")

    lines.extend(["", "## Checks", "", "| Status | Check | Actual | Expected | Detail |", "|---|---|---|---|---|"])
    for item in report.results:
        values = [
            item.status.value,
            item.name,
            item.actual,
            item.expected,
            item.detail,
        ]
        escaped = [v.replace("|", "\\|").replace("\n", " ") for v in values]
        lines.append("| " + " | ".join(escaped) + " |")
    lines.append("")
    return "\n".join(lines)


def write_report(report: QCReport, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_markdown(report), encoding="utf-8")
    return destination
