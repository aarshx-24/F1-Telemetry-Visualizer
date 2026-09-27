from __future__ import annotations

import numpy as np
import pandas as pd

from telemetry.domain import LapTelemetry
from telemetry.processing.schemas import DEFAULT_COMPARISON_CHANNELS


class DistanceTelemetryAligner:
    """Align lap telemetry on distance so driver traces are comparable."""

    def align_pair(
        self,
        reference: LapTelemetry,
        comparison: LapTelemetry,
        *,
        channels: tuple[str, ...] = DEFAULT_COMPARISON_CHANNELS,
        samples: int = 1200,
    ) -> pd.DataFrame:
        ref = reference.telemetry
        cmp = comparison.telemetry

        if "Distance" not in ref.columns or "Distance" not in cmp.columns:
            return pd.DataFrame()

        start = max(float(ref["Distance"].min()), float(cmp["Distance"].min()))
        end = min(float(ref["Distance"].max()), float(cmp["Distance"].max()))
        if end <= start:
            return pd.DataFrame()

        grid = np.linspace(start, end, samples)
        aligned = pd.DataFrame({"Distance": grid})

        for channel in channels:
            if channel in ref.columns:
                aligned[f"{reference.driver}_{channel}"] = self._interpolate(ref, channel, grid)
            if channel in cmp.columns:
                aligned[f"{comparison.driver}_{channel}"] = self._interpolate(cmp, channel, grid)

        ref_time = f"{reference.driver}_TimeSeconds"
        cmp_time = f"{comparison.driver}_TimeSeconds"
        if ref_time in aligned.columns and cmp_time in aligned.columns:
            aligned["DeltaSeconds"] = aligned[cmp_time] - aligned[ref_time]

        return aligned

    def align_many(
        self,
        laps: list[LapTelemetry],
        *,
        channels: tuple[str, ...] = DEFAULT_COMPARISON_CHANNELS,
        samples: int = 1200,
    ) -> pd.DataFrame:
        if not laps:
            return pd.DataFrame()

        start = max(float(lap.telemetry["Distance"].min()) for lap in laps)
        end = min(float(lap.telemetry["Distance"].max()) for lap in laps)
        if end <= start:
            return pd.DataFrame()

        grid = np.linspace(start, end, samples)
        aligned = pd.DataFrame({"Distance": grid})
        for lap in laps:
            for channel in channels:
                if channel in lap.telemetry.columns:
                    aligned[f"{lap.driver}_{channel}"] = self._interpolate(
                        lap.telemetry,
                        channel,
                        grid,
                    )

        return aligned

    @staticmethod
    def _interpolate(frame: pd.DataFrame, channel: str, grid: np.ndarray) -> np.ndarray:
        clean = frame[["Distance", channel]].dropna().drop_duplicates("Distance")
        if len(clean) < 2:
            return np.full_like(grid, np.nan, dtype=float)
        return np.interp(
            grid,
            clean["Distance"].astype(float).to_numpy(),
            clean[channel].astype(float).to_numpy(),
        )
