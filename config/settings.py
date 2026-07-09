from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectSettings:
    """Centralized filesystem settings for the telemetry platform."""

    project_root: Path
    raw_data_dir: Path
    processed_data_dir: Path
    cache_dir: Path
    reports_dir: Path

    def ensure_directories(self) -> None:
        for directory in (
            self.raw_data_dir,
            self.processed_data_dir,
            self.cache_dir,
            self.reports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def build_settings(project_root: Path | None = None) -> ProjectSettings:
    root = project_root or Path(__file__).resolve().parents[1]
    data_dir = root / "data"

    return ProjectSettings(
        project_root=root,
        raw_data_dir=data_dir / "raw",
        processed_data_dir=data_dir / "processed",
        cache_dir=data_dir / "cache",
        reports_dir=root / "reports",
    )
