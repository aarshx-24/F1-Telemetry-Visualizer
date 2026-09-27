"""Distance-weighted driving features from real available telemetry only."""

import numpy as np
import pandas as pd

from telemetry.domain import LapTelemetry

DRIVING_FEATURES = (
    "MeanSpeed",
    "MinSpeed",
    "ThrottleMean",
    "BrakeDistanceShare",
    "FullThrottleShare",
)


def driving_features(laps: list[LapTelemetry]) -> pd.DataFrame:
    rows = []
    for lap in laps:
        frame = lap.telemetry.sort_values("Distance").drop_duplicates("Distance")
        row = {"Driver": lap.driver, "LapNumber": lap.lap_number}
        if len(frame) < 2:
            continue
        weights = np.diff(frame["Distance"].to_numpy(dtype=float))
        if not np.isfinite(weights).all() or weights.sum() <= 0:
            continue
        for channel, target, threshold in [
            ("Speed", "MeanSpeed", None),
            ("Throttle", "ThrottleMean", None),
            ("Brake", "BrakeDistanceShare", 0.5),
            ("Throttle", "FullThrottleShare", 95),
        ]:
            if channel not in frame:
                continue
            values = pd.to_numeric(frame[channel], errors="coerce").to_numpy()[:-1]
            valid = np.isfinite(values)
            if valid.any():
                measured = (
                    values[valid]
                    if threshold is None
                    else (values[valid] > threshold).astype(float)
                )
                row[target] = float(np.average(measured, weights=weights[valid]))
        if "Speed" in frame:
            row["MinSpeed"] = float(frame["Speed"].min())
        rows.append(row)
    return pd.DataFrame(rows)
