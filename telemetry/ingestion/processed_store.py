from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import numpy as np

from telemetry.analytics.insights import DriverInsightEngine
from telemetry.domain import ComparisonResult, LapTelemetry, SessionRequest
from telemetry.processing import DistanceTelemetryAligner


DATASET_VERSION = 2


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
        return list(
            dict.fromkeys(str(lap["driver"]) for lap in manifest.get("laps", []))
        )

    def metadata(self, request: SessionRequest) -> list[dict[str, Any]]:
        return self._read_manifest(request)["laps"]

    def generated_at(self, request: SessionRequest) -> str:
        return str(self._read_manifest(request).get("generated_at", "unknown"))

    def list_requests(self) -> list[SessionRequest]:
        requests = []
        for path in self._root.glob("*/manifest.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))["request"]
                request = SessionRequest(**raw)
                if self.contains(request):
                    requests.append(request)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return requests

    def contains(
        self,
        request: SessionRequest,
        drivers: list[str] | None = None,
    ) -> bool:
        try:
            available = set(self.available_drivers(request))
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return bool(available) and (not drivers or set(drivers).issubset(available))

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

        generation = uuid4().hex
        laps_file, corners_file = f"laps_{generation}.csv", f"corners_{generation}.csv"
        lap_table.to_csv(session_dir / laps_file, index=False)
        corners.to_csv(session_dir / corners_file, index=False)

        sectors = (
            comparison.sector_table.set_index("Driver").to_dict(orient="index")
            if not comparison.sector_table.empty
            else {}
        )
        try:
            lap_metadata = self.metadata(comparison.request)
        except (OSError, ValueError, KeyError, TypeError):
            lap_metadata = []
        for lap in comparison.laps:
            telemetry_file = (
                f"telemetry/{generation}_{lap.lap_number}_{len(lap_metadata)}.csv"
            )
            lap.telemetry.to_csv(session_dir / telemetry_file, index=False)
            sector = sectors.get(lap.driver, {})
            lap_metadata = [
                item
                for item in lap_metadata
                if (item["driver"], item["lap_number"]) != (lap.driver, lap.lap_number)
            ]
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
            "laps_file": laps_file,
            "corners_file": corners_file,
            "laps": lap_metadata,
        }
        pending = session_dir / f"manifest_{generation}.tmp"
        pending.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        # Publish a complete generation atomically; readers never see partial CSVs.
        pending.replace(session_dir / "manifest.json")
        return session_dir

    def load_session(self, request: SessionRequest) -> ProcessedSession:
        session_dir = self._session_dir(request)
        manifest = self._read_manifest(request)
        return ProcessedSession(
            laps=pd.read_csv(
                _safe_path(session_dir, manifest.get("laps_file", "laps.csv"))
            ),
            corners=_read_optional_csv(
                _safe_path(session_dir, manifest.get("corners_file", "corners.csv"))
            ),
        )

    def load_comparison(
        self,
        request: SessionRequest,
        drivers: list[str],
        *,
        selections: dict[str, int] | None = None,
    ) -> ComparisonResult:
        if len(drivers) < 2:
            raise ValueError("At least two drivers are required for comparison.")

        manifest = self._read_manifest(request)
        metadata = {}
        for driver in drivers:
            options = [item for item in manifest["laps"] if item["driver"] == driver]
            if selections and driver in selections:
                options = [
                    item
                    for item in options
                    if int(item["lap_number"]) == selections[driver]
                ]
            if options:
                metadata[driver] = min(
                    options, key=lambda item: float(item["lap_time_seconds"])
                )
        missing = [driver for driver in drivers if driver not in metadata]
        if missing:
            raise ValueError(
                f"Processed telemetry is missing drivers: {', '.join(missing)}"
            )

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
        if not isinstance(manifest, dict):
            raise ValueError("Dataset manifest must be an object.")
        if manifest.get("dataset_version") not in (1, DATASET_VERSION):
            raise ValueError(f"Unsupported processed telemetry dataset: {path}")
        if not isinstance(manifest.get("laps"), list) or not manifest["laps"]:
            raise ValueError("Dataset has no telemetry metadata.")
        stored = manifest.get("request", {})
        if (
            stored.get("year") != request.year
            or _slug(str(stored.get("grand_prix", ""))) != _slug(request.grand_prix)
            or stored.get("session_type") != request.session_type
        ):
            raise ValueError("Dataset identity does not match the requested session.")
        for item in manifest["laps"]:
            if not isinstance(item, dict) or not {
                "driver",
                "lap_number",
                "telemetry_file",
                "lap_time_seconds",
            }.issubset(item):
                raise ValueError("Dataset lap metadata is incomplete.")
            if not _safe_path(path.parent, item["telemetry_file"]).is_file():
                raise ValueError("Dataset telemetry file is missing.")
        return manifest

    def load_laps(self, request: SessionRequest) -> list[LapTelemetry]:
        return [
            _load_lap(self._session_dir(request), row) for row in self.metadata(request)
        ]

    def _session_dir(self, request: SessionRequest) -> Path:
        return self._root / (
            f"{request.year}_{_slug(request.grand_prix)}_{_slug(request.session_type)}"
        )


def _load_lap(session_dir: Path, metadata: dict[str, Any]) -> LapTelemetry:
    frame = pd.read_csv(_safe_path(session_dir, str(metadata["telemetry_file"])))
    required = ["Distance", "TimeSeconds", "Speed"]
    if not set(required).issubset(frame) or len(frame) < 2:
        raise ValueError("Telemetry channels are incomplete.")
    if (
        not np.isfinite(frame[required].to_numpy(dtype=float)).all()
        or frame["Distance"].max() <= frame["Distance"].min()
    ):
        raise ValueError("Telemetry contains invalid samples.")
    if "DRS" in frame and "DRSActive" not in frame:
        frame["DRSActive"] = (
            frame["DRS"].isin([10, 12, 14]).astype(float).where(frame["DRS"].notna())
        )
    return LapTelemetry(
        driver=str(metadata["driver"]),
        lap_number=int(metadata["lap_number"]),
        lap_time_seconds=float(metadata["lap_time_seconds"]),
        team=str(metadata["team"]),
        compound=str(metadata["compound"]),
        stint=_optional_int(metadata.get("stint")),
        telemetry=frame,
    )


def _read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Dataset path escapes its session directory.")
    return path


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
        character.lower() if character.isalnum() else "_" for character in value
    ).strip("_")
