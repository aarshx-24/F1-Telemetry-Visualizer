"""Stint trends with conditional OLS uncertainty and explicit fuel scenarios."""

import numpy as np
import pandas as pd
from scipy.stats import linregress, t


class StintTrendAnalyzer:
    def summarize(
        self, laps: pd.DataFrame, *, fuel_gain_s_per_lap: float = 0.0
    ) -> pd.DataFrame:
        required = {"Driver", "Stint", "Compound", "LapNumber", "LapTimeSeconds"}
        if not required.issubset(laps):
            return pd.DataFrame()
        if not np.isfinite(fuel_gain_s_per_lap) or fuel_gain_s_per_lap < 0:
            raise ValueError("Fuel gain must be a nonnegative finite assumption.")
        rows = []
        for (driver, stint, compound), group in laps.groupby(
            ["Driver", "Stint", "Compound"], dropna=False
        ):
            group = group.copy()
            columns = ["LapNumber", "LapTimeSeconds"]
            group[columns] = (
                group[columns]
                .apply(pd.to_numeric, errors="coerce")
                .replace([np.inf, -np.inf], np.nan)
            )
            group = group.dropna(subset=columns).drop_duplicates("LapNumber")
            if len(group) < 4 or group["LapNumber"].nunique() < 4:
                continue
            x = group["LapNumber"].to_numpy(dtype=float)
            raw = group["LapTimeSeconds"].to_numpy(dtype=float)
            # Fuel burn makes later laps faster; add back an assumed time gain.
            y = raw + fuel_gain_s_per_lap * (x - x.min())
            fit = linregress(x, y)
            margin = float(t.ppf(0.975, len(x) - 2) * fit.stderr)
            rows.append(
                {
                    "Driver": driver,
                    "Stint": stint,
                    "Compound": compound,
                    "Laps": len(x),
                    "DegradationPerLap": fit.slope,
                    "Lower95": fit.slope - margin,
                    "Upper95": fit.slope + margin,
                    "R2": fit.rvalue**2,
                    "RawTrend": fit.slope - fuel_gain_s_per_lap,
                    "AssumedFuelGain": fuel_gain_s_per_lap,
                    "Model": "Conditional OLS lap-time trend",
                    "BestLap": raw.min(),
                    "MeanLap": raw.mean(),
                }
            )
        return pd.DataFrame(rows)
