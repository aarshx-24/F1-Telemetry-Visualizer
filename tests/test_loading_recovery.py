import json
import subprocess
from dataclasses import replace
from unittest.mock import Mock

from config.settings import build_settings
from telemetry.application.sessions import SessionService
from telemetry.domain import SessionRequest
from telemetry.ingestion.demo_data import DemoTelemetryFactory
from telemetry.ingestion.live_client import LiveSessionClient
from telemetry.ingestion.processed_store import ProcessedTelemetryStore

REQUEST = SessionRequest(2024, "Test Grand Prix", "Q")


def seed(store):
    factory = DemoTelemetryFactory()
    comparison = factory.build_comparison(REQUEST, ["VER", "LEC"])
    session = factory.build_session(["VER", "LEC"])
    path = store.save(
        comparison, session.laps, session.get_circuit_info().corners, frequency_hz=10
    )
    return path, comparison, session


def test_download_timeout_is_bounded_and_cooldown_blocks_retry(tmp_path, monkeypatch):
    run = Mock(side_effect=subprocess.TimeoutExpired("worker", 1))
    monkeypatch.setattr("telemetry.ingestion.live_client.subprocess.run", run)
    client = LiveSessionClient(build_settings(tmp_path), timeout_seconds=1)
    assert not client.fetch(REQUEST)
    assert not client.fetch(REQUEST)
    assert run.call_count == 1
    assert run.call_args.kwargs["timeout"] == 1


def test_worker_failure_is_not_success(tmp_path, monkeypatch):
    run = Mock(
        return_value=subprocess.CompletedProcess([], 1, "", "upstream unavailable")
    )
    monkeypatch.setattr("telemetry.ingestion.live_client.subprocess.run", run)
    assert not LiveSessionClient(build_settings(tmp_path)).fetch(REQUEST)


def test_loader_accepts_car_data_without_position_feed(tmp_path, monkeypatch):
    import pandas as pd
    from types import SimpleNamespace
    from telemetry.ingestion.fastf1_session_loader import FastF1SessionLoader

    session = SimpleNamespace(
        laps=pd.DataFrame({"Driver": ["VER"]}),
        car_data={"1": pd.DataFrame({"Speed": [200]})},
        load=Mock(),
    )
    fastf1 = Mock()
    fastf1.get_session.return_value = session
    loader = FastF1SessionLoader(build_settings(tmp_path))
    monkeypatch.setattr(loader, "_load_fastf1", lambda: fastf1)
    monkeypatch.setattr(loader, "_configure_cache", lambda _: None)
    assert loader.load_session(REQUEST) is session


def test_loader_does_not_retry_http_rate_limit(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from telemetry.ingestion.fastf1_session_loader import (
        FastF1SessionLoader,
        FastF1DataLoadError,
    )

    error = RuntimeError("rate limited")
    error.response = SimpleNamespace(status_code=429)
    fastf1 = Mock()
    fastf1.get_session.side_effect = error
    loader = FastF1SessionLoader(build_settings(tmp_path))
    monkeypatch.setattr(loader, "_load_fastf1", lambda: fastf1)
    monkeypatch.setattr(loader, "_configure_cache", lambda _: None)
    with pytest.raises(FastF1DataLoadError):
        loader.load_session(REQUEST)
    assert fastf1.get_session.call_count == 1


def test_archive_opens_without_network_and_survives_failed_refresh(tmp_path):
    settings = build_settings(tmp_path)
    seed(ProcessedTelemetryStore(settings.processed_data_dir / "prebuilt"))
    client = Mock()
    client.fetch.return_value = False
    service = SessionService(settings, client)
    dataset = service.open(REQUEST)
    client.fetch.assert_not_called()
    assert dataset is not None
    assert service.open(REQUEST, refresh=True) is not None
    client.fetch.assert_called_once()


def test_failure_without_archive_returns_no_fabricated_data(tmp_path):
    client = Mock()
    client.fetch.side_effect = OSError("offline")
    assert SessionService(build_settings(tmp_path), client).open(REQUEST) is None


def test_corrupt_downloaded_archive_falls_back_to_prepared(tmp_path):
    settings = build_settings(tmp_path)
    seed(ProcessedTelemetryStore(settings.processed_data_dir / "prebuilt"))
    path, _, _ = seed(
        ProcessedTelemetryStore(settings.processed_data_dir / "downloaded")
    )
    (path / "manifest.json").write_text("broken")
    dataset = SessionService(settings, Mock()).open(REQUEST)
    assert dataset.source == "Prepared FastF1 archive"


def test_store_preserves_previous_laps_on_atomic_generation(tmp_path):
    store = ProcessedTelemetryStore(tmp_path)
    path, comparison, session = seed(store)
    original = json.loads((path / "manifest.json").read_text())
    modified = replace(
        comparison,
        laps=tuple(
            replace(lap, lap_number=lap.lap_number + 10) for lap in comparison.laps
        ),
    )
    store.save(
        modified, session.laps, session.get_circuit_info().corners, frequency_hz=10
    )
    assert len(store.metadata(REQUEST)) == 4
    assert (path / original["laps_file"]).exists()
    loaded = store.load_comparison(
        REQUEST, ["VER", "LEC"], selections={"VER": 18, "LEC": 19}
    )
    assert [lap.lap_number for lap in loaded.laps] == [18, 19]


def test_manifest_path_traversal_rejected(tmp_path):
    store = ProcessedTelemetryStore(tmp_path)
    path, _, _ = seed(store)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["laps"][0]["telemetry_file"] = "../outside.csv"
    (path / "manifest.json").write_text(json.dumps(manifest))
    assert not store.contains(REQUEST)


def test_existing_v1_archive_is_readable():
    store = ProcessedTelemetryStore(build_settings().processed_data_dir / "prebuilt")
    request = SessionRequest(2024, "Italian Grand Prix", "Q")
    assert store.contains(request)
    result = store.load_comparison(request, ["VER", "LEC"])
    assert len(result.laps) == 2


def test_interrupted_manifest_publication_keeps_previous_generation(
    tmp_path, monkeypatch
):
    from pathlib import Path
    import pytest

    store = ProcessedTelemetryStore(tmp_path)
    path, comparison, session = seed(store)
    original = (path / "manifest.json").read_text()
    monkeypatch.setattr(
        Path, "replace", Mock(side_effect=OSError("interrupted publication"))
    )
    with pytest.raises(OSError):
        store.save(
            comparison,
            session.laps,
            session.get_circuit_info().corners,
            frequency_hz=10,
        )
    assert (path / "manifest.json").read_text() == original
    assert store.load_comparison(REQUEST, ["VER", "LEC"]).laps
