from pathlib import Path

from config.settings import build_settings


def test_settings_paths_are_under_project_root(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)

    assert settings.raw_data_dir == tmp_path / "data" / "raw"
    assert settings.processed_data_dir == tmp_path / "data" / "processed"
    assert settings.cache_dir == tmp_path / "data" / "cache"
    assert settings.reports_dir == tmp_path / "reports"


def test_ensure_directories_creates_required_directories(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)

    settings.ensure_directories()

    assert settings.raw_data_dir.is_dir()
    assert settings.processed_data_dir.is_dir()
    assert settings.cache_dir.is_dir()
    assert settings.reports_dir.is_dir()
