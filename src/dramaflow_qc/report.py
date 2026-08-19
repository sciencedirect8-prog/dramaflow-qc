from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dramaflow_qc import __version__
from dramaflow_qc.models import QCReport, Status

JSON_SCHEMA_VERSION = "1.0"


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


def report_to_dict(report: QCReport, generated_at: datetime | str | None = None) -> dict[str, object]:
    if generated_at is None:
        generated_at_value = datetime.now(timezone.utc).isoformat()
    elif isinstance(generated_at, datetime):
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        generated_at_value = generated_at.astimezone(timezone.utc).isoformat()
    else:
        generated_at_value = generated_at

    summary = {
        "total": len(report.results),
        "pass": 0,
        "warning": 0,
        "fail": 0,
        "info": 0,
    }
    for item in report.results:
        if item.status == Status.PASS:
            summary["pass"] += 1
        elif item.status == Status.WARNING:
            summary["warning"] += 1
        elif item.status == Status.FAIL:
            summary["fail"] += 1
        elif item.status == Status.INFO:
            summary["info"] += 1

    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "tool_version": __version__,
        "generated_at": generated_at_value,
        "target": report.target,
        "final_status": report.final_status.value,
        "sha256": report.sha256,
        "summary": summary,
        "checks": [
            {
                "name": item.name,
                "status": item.status.value,
                "actual": item.actual,
                "expected": item.expected,
                "detail": item.detail,
            }
            for item in report.results
        ],
    }


def render_json(report: QCReport, generated_at: datetime | str | None = None) -> str:
    return json.dumps(report_to_dict(report, generated_at=generated_at), ensure_ascii=False, indent=2) + "\n"


def write_json_report(report: QCReport, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_json(report), encoding="utf-8")
    return destination
