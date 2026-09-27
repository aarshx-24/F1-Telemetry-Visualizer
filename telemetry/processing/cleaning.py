from __future__ import annotations

import pandas as pd

from telemetry.processing.schemas import CAR_CHANNELS, POSITION_CHANNELS
from utils.time import add_seconds_column


class TelemetryCleaner:
    """Prepare FastF1 telemetry for comparison and visualization."""

    def prepare_lap_telemetry(self, telemetry: pd.DataFrame) -> pd.DataFrame:
        telemetry = self._add_distance_if_available(telemetry)
        frame = pd.DataFrame(telemetry).copy()
        frame = add_seconds_column(frame, "Time", "TimeSeconds")
        frame = add_seconds_column(frame, "SessionTime", "SessionTimeSeconds")
        frame = self._coerce_numeric_channels(frame)
        frame = self._normalize_binary_channels(frame)
        frame = self._sort_by_distance(frame)

        return frame.reset_index(drop=True)

    @staticmethod
    def _add_distance_if_available(frame: pd.DataFrame) -> pd.DataFrame:
        if "Distance" in frame.columns:
            return frame

        add_distance = getattr(frame, "add_distance", None)
        if add_distance is None:
            return frame
        return add_distance()

    @staticmethod
    def _coerce_numeric_channels(frame: pd.DataFrame) -> pd.DataFrame:
        numeric_columns = (
            "Distance",
            "RelativeDistance",
            "TimeSeconds",
            "SessionTimeSeconds",
            *CAR_CHANNELS,
            *POSITION_CHANNELS,
        )
        for column in numeric_columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    @staticmethod
    def _normalize_binary_channels(frame: pd.DataFrame) -> pd.DataFrame:
        if "Brake" in frame.columns:
            frame["Brake"] = (
                frame["Brake"]
                .astype(float)
                .where(frame["Brake"].isna(), (frame["Brake"] > 0.5).astype(float))
            )

        if "DRS" in frame.columns:
            frame["DRSActive"] = (
                frame["DRS"]
                .isin([10, 12, 14])
                .astype(float)
                .where(frame["DRS"].notna())
            )

        return frame

    @staticmethod
    def _sort_by_distance(frame: pd.DataFrame) -> pd.DataFrame:
        if "Distance" not in frame.columns:
            return frame

        frame = frame.dropna(subset=["Distance"]).sort_values("Distance")
        frame = frame.drop_duplicates(subset=["Distance"], keep="first")
        return frame
