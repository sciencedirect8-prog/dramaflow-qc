from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_NAME = ".dramaflow-qc.json"


@dataclass(slots=True)
class VideoRules:
    width: int = 1080
    height: int = 1920
    fps: float = 24.0
    video_codec: str = "h264"
    audio_sample_rate: int = 48000
    target_lufs: float = -16.0
    lufs_tolerance: float = 1.5


@dataclass(slots=True)
class ProjectRules:
    required_paths: list[str] = field(default_factory=lambda: ["QC_REPORTS"])
    filename_regex: str = r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(mp4|mov|mkv)$"


@dataclass(slots=True)
class AppConfig:
    video: VideoRules = field(default_factory=VideoRules)
    project: ProjectRules = field(default_factory=ProjectRules)


def default_config() -> AppConfig:
    return AppConfig()


def write_default_config(root: Path, overwrite: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / CONFIG_NAME
    if path.exists() and not overwrite:
        raise FileExistsError(f"Config already exists: {path}")
    path.write_text(json.dumps(asdict(default_config()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_config(start: Path | None = None) -> AppConfig:
    start = (start or Path.cwd()).resolve()
    candidates = [start] + list(start.parents)
    for folder in candidates:
        path = folder / CONFIG_NAME
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return AppConfig(
                video=VideoRules(**data.get("video", {})),
                project=ProjectRules(**data.get("project", {})),
            )
    return default_config()
