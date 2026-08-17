from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dramaflow_qc import __version__
from dramaflow_qc.config import CONFIG_NAME, load_config, write_default_config
from dramaflow_qc.hash_utils import sha256_file
from dramaflow_qc.inspectors.media import inspect_media
from dramaflow_qc.inspectors.project import inspect_filename, inspect_project
from dramaflow_qc.models import QCReport, Status
from dramaflow_qc.report import render_markdown, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dramaflow-qc", description="Quality-control CLI for AI video production.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init", help=f"Create {CONFIG_NAME} in a project directory.")
    init_cmd.add_argument("directory", nargs="?", default=".")
    init_cmd.add_argument("--force", action="store_true")

    check_cmd = sub.add_parser("check", help="Check one media file and write a Markdown QC report.")
    check_cmd.add_argument("file")
    check_cmd.add_argument("--report", help="Report path. Defaults to QC_REPORTS/<filename>_QC.md")
    check_cmd.add_argument("--no-loudness", action="store_true", help="Skip EBU R128 loudness analysis.")
    check_cmd.add_argument(
        "--decode-integrity",
        action="store_true",
        help="Run an opt-in full FFmpeg decode integrity check.",
    )

    project_cmd = sub.add_parser("project", help="Check project-level required paths.")
    project_cmd.add_argument("directory", nargs="?", default=".")
    project_cmd.add_argument("--report", help="Optional Markdown report path.")
    return parser


def _exit_code(status: Status) -> int:
    return 2 if status == Status.FAIL else 0


def cmd_init(args: argparse.Namespace) -> int:
    path = write_default_config(Path(args.directory).resolve(), overwrite=args.force)
    print(f"Created {path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    cfg = load_config(path.parent)
    results = [inspect_filename(path, cfg.project)]
    results.extend(inspect_media(
        path,
        cfg.video,
        check_loudness=not args.no_loudness,
        check_decode=args.decode_integrity,
    ))
    report = QCReport(target=str(path), results=results, sha256=sha256_file(path))

    if args.report:
        destination = Path(args.report).resolve()
    else:
        destination = path.parent / "QC_REPORTS" / f"{path.stem}_QC.md"
    write_report(report, destination)
    print(render_markdown(report))
    print(f"Report: {destination}")
    return _exit_code(report.final_status)


def cmd_project(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    if not root.is_dir():
        print(f"ERROR: directory not found: {root}", file=sys.stderr)
        return 2
    cfg = load_config(root)
    report = QCReport(target=str(root), results=inspect_project(root, cfg.project))
    print(render_markdown(report))
    if args.report:
        destination = write_report(report, Path(args.report).resolve())
        print(f"Report: {destination}")
    return _exit_code(report.final_status)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "project":
        return cmd_project(args)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
