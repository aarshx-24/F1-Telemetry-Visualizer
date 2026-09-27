from __future__ import annotations

import numpy as np
import pandas as pd

from telemetry.domain import LapTelemetry
from telemetry.processing.schemas import DEFAULT_COMPARISON_CHANNELS


class DistanceTelemetryAligner:
    """Align lap telemetry on distance so driver traces are comparable."""

    def align_reference(
        self, laps: list[LapTelemetry], reference_driver: str, *, samples: int = 1200
    ) -> pd.DataFrame:
        if reference_driver not in [lap.driver for lap in laps]:
            raise ValueError("Reference driver must be selected.")
        aligned = self.align_many(laps, samples=samples)
        ref = f"{reference_driver}_TimeSeconds"
        if ref in aligned:
            for lap in laps:
                key = f"{lap.driver}_TimeSeconds"
                if lap.driver != reference_driver and key in aligned:
                    aligned[f"Delta_{lap.driver}"] = aligned[key] - aligned[ref]
        aligned.attrs["reference_driver"] = reference_driver
        aligned.attrs["driver_order"] = [lap.driver for lap in laps]
        return aligned

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
        columns: dict[str, np.ndarray] = {"Distance": grid}

        for channel in channels:
            if channel in ref.columns:
                columns[f"{reference.driver}_{channel}"] = self._interpolate(
                    ref,
                    channel,
                    grid,
                )
            if channel in cmp.columns:
                columns[f"{comparison.driver}_{channel}"] = self._interpolate(
                    cmp,
                    channel,
                    grid,
                )

        ref_time = f"{reference.driver}_TimeSeconds"
        cmp_time = f"{comparison.driver}_TimeSeconds"
        if ref_time in columns and cmp_time in columns:
            columns["DeltaSeconds"] = columns[cmp_time] - columns[ref_time]

        return pd.DataFrame(columns)

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
        columns: dict[str, np.ndarray] = {"Distance": grid}
        for lap in laps:
            for channel in channels:
                if channel in lap.telemetry.columns:
                    columns[f"{lap.driver}_{channel}"] = self._interpolate(
                        lap.telemetry,
                        channel,
                        grid,
                    )

        return pd.DataFrame(columns)

    @staticmethod
    def _interpolate(frame: pd.DataFrame, channel: str, grid: np.ndarray) -> np.ndarray:
        clean = (
            frame[["Distance", channel]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            .drop_duplicates("Distance")
            .sort_values("Distance")
        )
        if len(clean) < 2:
            return np.full_like(grid, np.nan, dtype=float)
        if channel in {"Brake", "nGear", "DRS", "DRSActive"}:
            indexes = (
                np.searchsorted(clean["Distance"].to_numpy(), grid, side="right") - 1
            )
            return clean[channel].to_numpy(dtype=float)[
                np.clip(indexes, 0, len(clean) - 1)
            ]
        return np.interp(
            grid,
            clean["Distance"].astype(float).to_numpy(),
            clean[channel].astype(float).to_numpy(),
        )
