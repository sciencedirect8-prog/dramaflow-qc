from __future__ import annotations

import re
from pathlib import Path

from dramaflow_qc.config import ProjectRules
from dramaflow_qc.models import CheckResult, Status


def inspect_project(root: Path, rules: ProjectRules) -> list[CheckResult]:
    results: list[CheckResult] = []
    for required in rules.required_paths:
        target = root / required
        results.append(CheckResult(
            f"Required path: {required}",
            Status.PASS if target.exists() else Status.FAIL,
            actual="exists" if target.exists() else "missing",
            expected="exists",
        ))
    return results


def inspect_filename(path: Path, rules: ProjectRules) -> CheckResult:
    try:
        matched = re.fullmatch(rules.filename_regex, path.name) is not None
    except re.error as exc:
        return CheckResult("Filename rule", Status.WARNING, detail=f"Invalid filename_regex: {exc}")
    return CheckResult(
        "Filename rule",
        Status.PASS if matched else Status.FAIL,
        actual=path.name,
        expected=rules.filename_regex,
    )
