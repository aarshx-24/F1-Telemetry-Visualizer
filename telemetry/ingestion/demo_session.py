"""Offline adapter for the bundled, real FastF1-derived demonstration fixture."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from telemetry.domain import SessionRequest

DEMO_SOURCE_REQUEST = SessionRequest(2024, "Bahrain Grand Prix", "Q")
DEMO_DIRECTORY = "2024_bahrain_grand_prix_q"


class DemoSession:
    """Small session-compatible object backed by versioned CSV telemetry exports."""

    def __init__(
        self,
        laps: pd.DataFrame,
        results: pd.DataFrame,
        telemetry_files: dict[tuple[str, int], Path],
        corners: pd.DataFrame,
    ) -> None:
        self.laps = laps
        self.results = results
        self.drivers = results["Abbreviation"].dropna().astype(str).tolist()
        self.event = {
            "EventName": DEMO_SOURCE_REQUEST.grand_prix,
            "RoundNumber": 1,
            "Location": "Sakhir",
        }
        self.name = "Qualifying"
        self.date = pd.Timestamp("2024-03-01")
        self._telemetry_files = telemetry_files
        self._circuit_info = SimpleNamespace(corners=corners)

    def get_lap_telemetry(
        self, lap: pd.Series, *, frequency: int | str | None = 10
    ) -> pd.DataFrame:
        key = (str(lap["Driver"]), int(lap["LapNumber"]))
        path = self._telemetry_files.get(key)
        if path is None:
            raise ValueError(
                f"Bundled telemetry is not available for {key[0]} lap {key[1]}."
            )
        frame = pd.read_csv(path)
        for column in ("Time", "SessionTime"):
            if column in frame:
                frame[column] = pd.to_timedelta(frame[column])
        requested_hz = _frequency(frequency)
        # The export was generated at 10 Hz. Lower rates use a true subset;
        # higher rates keep the original real samples rather than inventing data.
        if requested_hz < 10:
            stride = max(1, round(10 / requested_hz))
            frame = frame.iloc[::stride].copy()
        return frame

    def get_circuit_info(self) -> SimpleNamespace:
        return self._circuit_info


class DemoSessionLoader:
    """Load the tracked real-data fixture without importing or contacting FastF1."""

    def __init__(self, project_root: Path) -> None:
        self._directory = project_root / "data" / "demo" / DEMO_DIRECTORY

    def load(self) -> DemoSession:
        manifest_path = self._directory / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                "The bundled demonstration telemetry fixture is missing."
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("request") != {
            "year": DEMO_SOURCE_REQUEST.year,
            "grand_prix": DEMO_SOURCE_REQUEST.grand_prix,
            "session_type": DEMO_SOURCE_REQUEST.session_type,
        }:
            raise ValueError("The bundled demonstration fixture metadata is invalid.")
        laps = pd.read_csv(self._directory / manifest["laps_file"])
        laps = _prepare_laps(laps)
        telemetry_files = {
            (str(item["driver"]), int(item["lap_number"])): self._directory
            / item["telemetry_file"]
            for item in manifest["laps"]
        }
        missing = [path for path in telemetry_files.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "The bundled demonstration telemetry files are incomplete."
            )
        metadata = pd.DataFrame(manifest["laps"])
        results = metadata[["driver", "team", "lap_time_seconds"]].rename(
            columns={
                "driver": "Abbreviation",
                "team": "TeamName",
                "lap_time_seconds": "BestLapTime",
            }
        )
        results.insert(0, "Position", range(1, len(results) + 1))
        corners = pd.read_csv(self._directory / manifest["corners_file"])
        return DemoSession(laps, results, telemetry_files, corners)


def _prepare_laps(laps: pd.DataFrame) -> pd.DataFrame:
    frame = laps.copy()
    for column in ("LapTime", "Sector1Time", "Sector2Time", "Sector3Time"):
        seconds = f"{column}Seconds"
        if seconds in frame:
            frame[column] = pd.to_timedelta(frame[seconds], unit="s")
    for column in ("PitOutTime", "PitInTime"):
        if column in frame:
            frame[column] = pd.to_timedelta(frame[column], errors="coerce")
    return frame


def _frequency(value: int | str | None) -> int:
    try:
        return max(1, int(value or 10))
    except (TypeError, ValueError):
        return 10
