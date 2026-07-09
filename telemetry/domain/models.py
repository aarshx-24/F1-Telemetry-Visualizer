from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


@dataclass(frozen=True, slots=True)
class SessionRequest:
    """A user-facing request for one F1 session."""

    year: int
    grand_prix: str
    session_type: str

    @property
    def label(self) -> str:
        return f"{self.year} {self.grand_prix} {self.session_type}"


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """Small domain object used to verify the ingestion boundary."""

    request: SessionRequest
    event_name: str
    session_name: str
    date: str
    circuit_name: str
    driver_count: int
    lap_count: int
    cache_path: str

    def to_console_text(self) -> str:
        return "\n".join(
            (
                "F1 Telemetry Visualizer - Session Summary",
                f"Request: {self.request.label}",
                f"Event: {self.event_name}",
                f"Session: {self.session_name}",
                f"Date: {self.date}",
                f"Circuit: {self.circuit_name}",
                f"Drivers loaded: {self.driver_count}",
                f"Laps loaded: {self.lap_count}",
                f"FastF1 cache: {self.cache_path}",
            )
        )


@dataclass(frozen=True, slots=True)
class LapTelemetry:
    """Telemetry and metadata for one selected lap."""

    driver: str
    lap_number: int
    lap_time_seconds: float
    team: str
    compound: str
    stint: int | None
    telemetry: pd.DataFrame

    @property
    def label(self) -> str:
        return f"{self.driver} L{self.lap_number} ({self.lap_time_seconds:.3f}s)"


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Aligned telemetry and metadata for a driver comparison."""

    request: SessionRequest
    laps: tuple[LapTelemetry, ...]
    aligned: pd.DataFrame
    sector_table: pd.DataFrame
    insights: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExportedReport:
    """Represents a generated local report artifact."""

    path: Path
    description: str
