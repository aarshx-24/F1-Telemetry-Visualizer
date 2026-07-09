from __future__ import annotations

import numpy as np
import pandas as pd

from telemetry.domain import LapTelemetry


class DriverInsightEngine:
    """Create concise racing insights from telemetry comparisons."""

    def build_driver_comparison_insights(
        self,
        laps: list[LapTelemetry],
        aligned: pd.DataFrame,
    ) -> list[str]:
        insights: list[str] = []
        if not laps:
            return insights

        fastest = min(laps, key=lambda lap: lap.lap_time_seconds)
        slowest = max(laps, key=lambda lap: lap.lap_time_seconds)
        if fastest.driver != slowest.driver:
            gap = slowest.lap_time_seconds - fastest.lap_time_seconds
            insights.append(
                f"{fastest.driver} owns the best selected lap by {gap:.3f}s over {slowest.driver}."
            )

        for lap in laps:
            telemetry = lap.telemetry
            if "Speed" in telemetry:
                insights.append(
                    f"{lap.driver} peak speed: {telemetry['Speed'].max():.1f} km/h; "
                    f"minimum speed: {telemetry['Speed'].min():.1f} km/h."
                )
            if "Throttle" in telemetry:
                full_throttle = float((telemetry["Throttle"] > 95).mean() * 100)
                insights.append(f"{lap.driver} full-throttle distance share: {full_throttle:.1f}%.")

        if "DeltaSeconds" in aligned:
            delta = aligned["DeltaSeconds"].dropna()
            if not delta.empty:
                direction = "behind" if delta.iloc[-1] > 0 else "ahead"
                insights.append(
                    f"Finish-line delta trend: comparison driver is {abs(delta.iloc[-1]):.3f}s {direction}."
                )

        return insights[:8]


class BrakingAnalyzer:
    """Detect braking zones and summarize braking efficiency indicators."""

    def detect_braking_zones(
        self,
        lap: LapTelemetry,
        *,
        minimum_distance_m: float = 20.0,
    ) -> pd.DataFrame:
        telemetry = lap.telemetry
        if "Brake" not in telemetry or "Distance" not in telemetry:
            return pd.DataFrame()

        frame = telemetry[["Distance", "Speed", "Brake", "TimeSeconds"]].copy()
        frame["Braking"] = frame["Brake"].fillna(0).astype(float) > 0.5
        frame["ZoneId"] = (frame["Braking"] != frame["Braking"].shift()).cumsum()

        rows: list[dict[str, float | int | str]] = []
        for _, zone in frame[frame["Braking"]].groupby("ZoneId"):
            distance = float(zone["Distance"].max() - zone["Distance"].min())
            if distance < minimum_distance_m:
                continue

            entry_speed = float(zone["Speed"].iloc[0])
            minimum_speed = float(zone["Speed"].min())
            speed_drop = entry_speed - minimum_speed
            duration = float(zone["TimeSeconds"].max() - zone["TimeSeconds"].min())
            efficiency = speed_drop / distance if distance > 0 else np.nan

            rows.append(
                {
                    "Driver": lap.driver,
                    "Lap": lap.lap_number,
                    "StartDistance": float(zone["Distance"].min()),
                    "EndDistance": float(zone["Distance"].max()),
                    "LengthM": distance,
                    "DurationS": duration,
                    "EntrySpeed": entry_speed,
                    "MinimumSpeed": minimum_speed,
                    "SpeedDrop": speed_drop,
                    "SpeedDropPerMeter": efficiency,
                }
            )

        return pd.DataFrame(rows).reset_index(drop=True)


class ConsistencyAnalyzer:
    """Compute driver consistency and pace spread from lap timing."""

    def summarize(self, lap_table: pd.DataFrame) -> pd.DataFrame:
        if lap_table.empty or "LapTimeSeconds" not in lap_table:
            return pd.DataFrame()

        timed = lap_table.dropna(subset=["LapTimeSeconds"]).copy()
        timed = timed[timed["LapTimeSeconds"] > 0]
        if timed.empty:
            return pd.DataFrame()

        grouped = timed.groupby("Driver")["LapTimeSeconds"]
        summary = grouped.agg(
            Laps="count",
            BestLap="min",
            MeanLap="mean",
            MedianLap="median",
            StdDev="std",
        ).reset_index()
        summary["ConsistencyScore"] = 100 / (1 + summary["StdDev"].fillna(0))
        return summary.sort_values(["BestLap", "StdDev"]).reset_index(drop=True)


class TireDegradationAnalyzer:
    """Estimate stint-level tyre degradation from lap-time trend."""

    def summarize(self, lap_table: pd.DataFrame, driver: str | None = None) -> pd.DataFrame:
        if lap_table.empty or "LapTimeSeconds" not in lap_table:
            return pd.DataFrame()

        data = lap_table.dropna(subset=["LapTimeSeconds"]).copy()
        if driver and "Driver" in data:
            data = data[data["Driver"] == driver]
        if data.empty or "Stint" not in data:
            return pd.DataFrame()

        rows: list[dict[str, object]] = []
        for keys, stint in data.groupby(["Driver", "Stint", "Compound"], dropna=False):
            if len(stint) < 3:
                continue
            x = stint["LapNumber"].astype(float).to_numpy()
            y = stint["LapTimeSeconds"].astype(float).to_numpy()
            slope = float(np.polyfit(x, y, deg=1)[0])
            rows.append(
                {
                    "Driver": keys[0],
                    "Stint": keys[1],
                    "Compound": keys[2],
                    "Laps": len(stint),
                    "BestLap": float(np.min(y)),
                    "MeanLap": float(np.mean(y)),
                    "DegradationPerLap": slope,
                }
            )
        return pd.DataFrame(rows).reset_index(drop=True)


class CornerPerformanceAnalyzer:
    """Summarize entry, apex, and exit speed around known circuit corners."""

    def summarize(
        self,
        lap: LapTelemetry,
        circuit_info: object | None,
        *,
        window_m: float = 70.0,
    ) -> pd.DataFrame:
        corners = getattr(circuit_info, "corners", None)
        telemetry = lap.telemetry
        if corners is None or "Distance" not in getattr(corners, "columns", []):
            return pd.DataFrame()
        if "Speed" not in telemetry or "Distance" not in telemetry:
            return pd.DataFrame()

        rows: list[dict[str, object]] = []
        for _, corner in pd.DataFrame(corners).iterrows():
            distance = float(corner["Distance"])
            segment = telemetry[
                telemetry["Distance"].between(distance - window_m, distance + window_m)
            ]
            if segment.empty:
                continue

            rows.append(
                {
                    "Driver": lap.driver,
                    "Corner": _corner_label(corner),
                    "Distance": distance,
                    "EntrySpeed": float(segment.iloc[0]["Speed"]),
                    "ApexMinimumSpeed": float(segment["Speed"].min()),
                    "ExitSpeed": float(segment.iloc[-1]["Speed"]),
                }
            )
        return pd.DataFrame(rows)


def _corner_label(corner: pd.Series) -> str:
    number = str(corner.get("Number", "")).strip()
    letter = str(corner.get("Letter", "")).strip()
    return f"{number}{letter}".strip()
