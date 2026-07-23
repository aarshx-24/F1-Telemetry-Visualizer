from pathlib import Path

from telemetry.domain import SessionRequest
from telemetry.ingestion.demo_data import DemoTelemetryFactory
from telemetry.ingestion.processed_store import ProcessedTelemetryStore


def test_processed_store_round_trip(tmp_path: Path) -> None:
    request = SessionRequest(2024, "Italian Grand Prix", "Q")
    factory = DemoTelemetryFactory()
    comparison = factory.build_comparison(request, ["VER", "LEC"])
    session = factory.build_session(["VER", "LEC"])
    corners = session.get_circuit_info().corners
    store = ProcessedTelemetryStore(tmp_path)

    output = store.save(
        comparison,
        session.laps,
        corners,
        frequency_hz=10,
    )

    assert (output / "manifest.json").is_file()
    assert store.contains(request, ["VER", "LEC"])
    assert store.available_drivers(request) == ["VER", "LEC"]

    loaded_session = store.load_session(request)
    loaded = store.load_comparison(request, ["VER", "LEC"])

    assert not loaded_session.laps.empty
    assert [lap.driver for lap in loaded.laps] == ["VER", "LEC"]
    assert "DeltaSeconds" in loaded.aligned
    assert loaded.sector_table["Driver"].tolist() == ["VER", "LEC"]
