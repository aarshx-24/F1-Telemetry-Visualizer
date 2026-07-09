from __future__ import annotations

from typing import Any

import pandas as pd

from telemetry.analytics.insights import DriverInsightEngine
from telemetry.domain import ComparisonResult, LapTelemetry, SessionRequest
from telemetry.processing import DistanceTelemetryAligner, TelemetryExtractor


class DriverComparisonService:
    """Coordinate lap extraction, sector comparison, and aligned telemetry."""

    def __init__(
        self,
        extractor: TelemetryExtractor | None = None,
        aligner: DistanceTelemetryAligner | None = None,
        insight_engine: DriverInsightEngine | None = None,
    ) -> None:
        self._extractor = extractor or TelemetryExtractor()
        self._aligner = aligner or DistanceTelemetryAligner()
        self._insight_engine = insight_engine or DriverInsightEngine()

    def compare_fastest_laps(
        self,
        session: Any,
        request: SessionRequest,
        drivers: list[str],
        *,
        frequency: int | str | None = 10,
    ) -> ComparisonResult:
        if len(drivers) < 2:
            raise ValueError("At least two drivers are required for comparison.")

        laps = self._extractor.extract_fastest_laps(
            session,
            drivers,
            frequency=frequency,
        )
        aligned = self._aligner.align_many(laps)

        if len(laps) == 2:
            aligned = self._aligner.align_pair(laps[0], laps[1])

        sector_table = self._extractor.sector_table(laps, session)
        insights = self._insight_engine.build_driver_comparison_insights(laps, aligned)

        return ComparisonResult(
            request=request,
            laps=tuple(laps),
            aligned=aligned,
            sector_table=sector_table,
            insights=tuple(insights),
        )

    @staticmethod
    def rank_by_lap_time(laps: list[LapTelemetry]) -> pd.DataFrame:
        rows = [
            {
                "Driver": lap.driver,
                "Lap": lap.lap_number,
                "LapTime": lap.lap_time_seconds,
                "Compound": lap.compound,
                "Team": lap.team,
            }
            for lap in laps
        ]
        return pd.DataFrame(rows).sort_values("LapTime").reset_index(drop=True)
