"""Auditable lap selection, independent of the UI and data provider."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class QualityPolicy:
    clean_only: bool = True
    green_only: bool = True
    pace_ratio: float | None = 1.07


@dataclass(frozen=True)
class QualityResult:
    accepted: pd.DataFrame
    audit: pd.DataFrame
    missing_metadata: tuple[str, ...]


def flag_true(values: pd.Series) -> pd.Series:
    return values.astype(str).str.lower().isin(["true", "1", "1.0"])


class LapQualityFilter:
    def apply(
        self, laps: pd.DataFrame, policy: QualityPolicy = QualityPolicy()
    ) -> QualityResult:
        data = laps.copy().reset_index(drop=True)
        reasons = pd.Series("", index=data.index, dtype=object)

        def reject(mask: pd.Series, reason: str) -> None:
            reasons.loc[mask.fillna(False)] += reason + "; "

        times = pd.to_numeric(
            data.get("LapTimeSeconds", pd.Series(index=data.index, dtype=float)),
            errors="coerce",
        )
        reject(~np.isfinite(times) | times.le(0), "invalid lap time")
        missing = []
        if policy.clean_only:
            for column in ("PitInTime", "PitOutTime", "Deleted", "IsAccurate"):
                if column not in data:
                    missing.append(column)
                    continue
                values = data[column]
                if column.startswith("Pit"):
                    reject(
                        values.notna()
                        & ~values.astype(str).isin(["", "NaT", "nan", "None"]),
                        column,
                    )
                elif column == "Deleted":
                    reject(flag_true(values), "deleted lap")
                else:
                    reject(values.notna() & ~flag_true(values), "inaccurate timing")
        if policy.green_only:
            if "TrackStatus" in data:
                status = (
                    data["TrackStatus"].astype(str).str.replace(r"\.0$", "", regex=True)
                )
                reject(status.ne("1"), "non-green or unknown track status")
            else:
                missing.append("TrackStatus")
        if policy.pace_ratio is not None and {"Driver", "Compound", "Stint"}.issubset(
            data
        ):
            if policy.pace_ratio < 1:
                raise ValueError("Pace ratio must be at least one.")
            eligible = data.loc[reasons.eq("")].copy()
            eligible["LapTimeSeconds"] = times.loc[eligible.index]
            best = eligible.groupby(["Driver", "Stint", "Compound"], dropna=False)[
                "LapTimeSeconds"
            ].transform("min")
            reject(
                times.gt(best.reindex(data.index) * policy.pace_ratio),
                "outside stint pace threshold",
            )
        data["LapTimeSeconds"] = times
        data["QualityReason"] = reasons.str.rstrip("; ")
        data["Included"] = reasons.eq("")
        return QualityResult(data.loc[data["Included"]].copy(), data, tuple(missing))
