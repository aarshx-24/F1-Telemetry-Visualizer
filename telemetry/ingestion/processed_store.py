from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from telemetry.analytics.insights import DriverInsightEngine
from telemetry.domain import ComparisonResult, LapTelemetry, SessionRequest
from telemetry.processing import DistanceTelemetryAligner


DATASET_VERSION = 1


@dataclass(frozen=True, slots=True)
class ProcessedSession:
    """Small session adapter used by analytics that need laps and circuit corners."""

    laps: pd.DataFrame
    corners: pd.DataFrame

    def get_circuit_info(self) -> object:
        return type("ProcessedCircuitInfo", (), {"corners": self.corners})()


class ProcessedTelemetryStore:
    """Persist analysis-ready telemetry independently from the FastF1 API."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def available_drivers(self, request: SessionRequest) -> list[str]:
        manifest = self._read_manifest(request)
        return [str(lap["driver"]) for lap in manifest.get("laps", [])]

    def contains(
        self,
        request: SessionRequest,
        drivers: list[str] | None = None,
    ) -> bool:
        try:
            available = set(self.available_drivers(request))
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            return False
        return not drivers or set(drivers).issubset(available)

    def save(
        self,
        comparison: ComparisonResult,
        lap_table: pd.DataFrame,
        corners: pd.DataFrame,
        *,
        frequency_hz: int,
    ) -> Path:
        session_dir = self._session_dir(comparison.request)
        telemetry_dir = session_dir / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)

        lap_table.to_csv(session_dir / "laps.csv", index=False)
        corners.to_csv(session_dir / "corners.csv", index=False)

        sectors = (
            comparison.sector_table.set_index("Driver").to_dict(orient="index")
            if not comparison.sector_table.empty
            else {}
        )
        lap_metadata: list[dict[str, object]] = []
        for lap in comparison.laps:
            telemetry_file = f"telemetry/{lap.driver}.csv"
            lap.telemetry.to_csv(session_dir / telemetry_file, index=False)
            sector = sectors.get(lap.driver, {})
            lap_metadata.append(
                {
                    "driver": lap.driver,
                    "lap_number": lap.lap_number,
                    "lap_time_seconds": lap.lap_time_seconds,
                    "team": lap.team,
                    "compound": lap.compound,
                    "stint": lap.stint,
                    "telemetry_file": telemetry_file,
                    "sector1": _optional_float(sector.get("Sector1")),
                    "sector2": _optional_float(sector.get("Sector2")),
                    "sector3": _optional_float(sector.get("Sector3")),
                }
            )

        manifest = {
            "dataset_version": DATASET_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "request": {
                "year": comparison.request.year,
                "grand_prix": comparison.request.grand_prix,
                "session_type": comparison.request.session_type,
            },
            "frequency_hz": frequency_hz,
            "laps": lap_metadata,
        }
        (session_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return session_dir

    def load_session(self, request: SessionRequest) -> ProcessedSession:
        session_dir = self._session_dir(request)
        return ProcessedSession(
            laps=pd.read_csv(session_dir / "laps.csv"),
            corners=_read_optional_csv(session_dir / "corners.csv"),
        )

    def load_comparison(
        self,
        request: SessionRequest,
        drivers: list[str],
    ) -> ComparisonResult:
        if len(drivers) < 2:
            raise ValueError("At least two drivers are required for comparison.")

        manifest = self._read_manifest(request)
        metadata = {str(item["driver"]): item for item in manifest["laps"]}
        missing = [driver for driver in drivers if driver not in metadata]
        if missing:
            raise ValueError(f"Processed telemetry is missing drivers: {', '.join(missing)}")

        session_dir = self._session_dir(request)
        laps = [_load_lap(session_dir, metadata[driver]) for driver in drivers]
        aligner = DistanceTelemetryAligner()
        aligned = (
            aligner.align_pair(laps[0], laps[1])
            if len(laps) == 2
            else aligner.align_many(laps)
        )
        sector_table = pd.DataFrame(
            [
                {
                    "Driver": lap.driver,
                    "Lap": lap.lap_number,
                    "LapTime": lap.lap_time_seconds,
                    "Sector1": metadata[lap.driver].get("sector1"),
                    "Sector2": metadata[lap.driver].get("sector2"),
                    "Sector3": metadata[lap.driver].get("sector3"),
                    "Compound": lap.compound,
                    "Team": lap.team,
                }
                for lap in laps
            ]
        )
        insights = DriverInsightEngine().build_driver_comparison_insights(laps, aligned)
        return ComparisonResult(
            request=request,
            laps=tuple(laps),
            aligned=aligned,
            sector_table=sector_table,
            insights=tuple(insights),
        )

    def _read_manifest(self, request: SessionRequest) -> dict[str, Any]:
        path = self._session_dir(request) / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("dataset_version") != DATASET_VERSION:
            raise ValueError(f"Unsupported processed telemetry dataset: {path}")
        return manifest

    def _session_dir(self, request: SessionRequest) -> Path:
        return self._root / (
            f"{request.year}_{_slug(request.grand_prix)}_"
            f"{_slug(request.session_type)}"
        )


def _load_lap(session_dir: Path, metadata: dict[str, Any]) -> LapTelemetry:
    return LapTelemetry(
        driver=str(metadata["driver"]),
        lap_number=int(metadata["lap_number"]),
        lap_time_seconds=float(metadata["lap_time_seconds"]),
        team=str(metadata["team"]),
        compound=str(metadata["compound"]),
        stint=_optional_int(metadata.get("stint")),
        telemetry=pd.read_csv(session_dir / str(metadata["telemetry_file"])),
    )


def _read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _slug(value: str) -> str:
    return "".join(
        character.lower() if character.isalnum() else "_"
        for character in value
    ).strip("_")
