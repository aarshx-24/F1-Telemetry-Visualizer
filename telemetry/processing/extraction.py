from __future__ import annotations

from typing import Any

import pandas as pd

from telemetry.domain import LapTelemetry
from telemetry.processing.cleaning import TelemetryCleaner
from telemetry.processing.schemas import LAP_TIME_COLUMNS
from utils.time import seconds


class TelemetryExtractionError(RuntimeError):
    """Raised when requested lap or driver data cannot be extracted."""


class TelemetryExtractor:
    """Extract domain-friendly lap and session data from FastF1 sessions."""

    def __init__(self, cleaner: TelemetryCleaner | None = None) -> None:
        self._cleaner = cleaner or TelemetryCleaner()

    def available_drivers(self, session: Any) -> list[str]:
        results = getattr(session, "results", None)
        if results is not None and "Abbreviation" in results:
            drivers = [str(driver) for driver in results["Abbreviation"].dropna()]
            if drivers:
                return drivers

        laps = getattr(session, "laps", pd.DataFrame())
        if "Driver" not in laps:
            return []
        return sorted(str(driver) for driver in laps["Driver"].dropna().unique())

    def lap_table(self, session: Any, driver: str | None = None) -> pd.DataFrame:
        laps = pd.DataFrame(getattr(session, "laps", pd.DataFrame())).copy()
        if laps.empty:
            return laps

        if driver and "Driver" in laps:
            laps = laps[laps["Driver"] == driver].copy()

        for column in LAP_TIME_COLUMNS:
            if column in laps.columns:
                laps[f"{column}Seconds"] = pd.to_timedelta(laps[column]).dt.total_seconds()

        useful_columns = [
            column
            for column in (
                "Driver",
                "LapNumber",
                "LapTimeSeconds",
                "Sector1TimeSeconds",
                "Sector2TimeSeconds",
                "Sector3TimeSeconds",
                "Compound",
                "TyreLife",
                "Stint",
                "Team",
                "TrackStatus",
                "PitOutTime",
                "PitInTime",
            )
            if column in laps.columns
        ]
        return laps[useful_columns].reset_index(drop=True)

    def extract_fastest_lap(
        self,
        session: Any,
        driver: str,
        *,
        frequency: int | str | None = 10,
    ) -> LapTelemetry:
        laps = self._driver_laps(session, driver)
        fast_lap = self._pick_fastest(laps)
        return self._build_lap_telemetry(fast_lap, frequency=frequency)

    def extract_lap(
        self,
        session: Any,
        driver: str,
        lap_number: int,
        *,
        frequency: int | str | None = 10,
    ) -> LapTelemetry:
        laps = self._driver_laps(session, driver)
        selected = laps[laps["LapNumber"].astype(int) == int(lap_number)]
        if selected.empty:
            raise TelemetryExtractionError(f"No lap {lap_number} found for {driver}.")
        return self._build_lap_telemetry(selected.iloc[0], frequency=frequency)

    def extract_fastest_laps(
        self,
        session: Any,
        drivers: list[str],
        *,
        frequency: int | str | None = 10,
    ) -> list[LapTelemetry]:
        return [
            self.extract_fastest_lap(session, driver, frequency=frequency)
            for driver in drivers
        ]

    def sector_table(self, laps: list[LapTelemetry], session: Any) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        for lap_telemetry in laps:
            lap = self._get_lap_row(
                session,
                lap_telemetry.driver,
                lap_telemetry.lap_number,
            )
            rows.append(
                {
                    "Driver": lap_telemetry.driver,
                    "Lap": lap_telemetry.lap_number,
                    "LapTime": lap_telemetry.lap_time_seconds,
                    "Sector1": seconds(lap.get("Sector1Time")),
                    "Sector2": seconds(lap.get("Sector2Time")),
                    "Sector3": seconds(lap.get("Sector3Time")),
                    "Compound": lap_telemetry.compound,
                    "Team": lap_telemetry.team,
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _driver_laps(session: Any, driver: str) -> pd.DataFrame:
        laps = getattr(session, "laps", pd.DataFrame())
        if laps.empty:
            raise TelemetryExtractionError("Session contains no lap data.")

        pick_drivers = getattr(laps, "pick_drivers", None)
        driver_laps = pick_drivers(driver) if pick_drivers else laps[laps["Driver"] == driver]
        driver_laps = driver_laps[driver_laps["LapTime"].notna()]

        if driver_laps.empty:
            raise TelemetryExtractionError(f"No timed laps found for driver {driver}.")

        return driver_laps

    @staticmethod
    def _pick_fastest(laps: pd.DataFrame) -> Any:
        pick_quicklaps = getattr(laps, "pick_quicklaps", None)
        quick_laps = pick_quicklaps() if pick_quicklaps else laps
        if quick_laps.empty:
            quick_laps = laps

        pick_fastest = getattr(quick_laps, "pick_fastest", None)
        if pick_fastest:
            return pick_fastest()

        return quick_laps.loc[quick_laps["LapTime"].idxmin()]

    def _build_lap_telemetry(
        self,
        lap: Any,
        *,
        frequency: int | str | None,
    ) -> LapTelemetry:
        get_telemetry = getattr(lap, "get_telemetry", None)
        if get_telemetry is None:
            raise TelemetryExtractionError("Selected lap cannot provide telemetry.")

        raw_telemetry = get_telemetry(frequency=frequency)
        telemetry = self._cleaner.prepare_lap_telemetry(raw_telemetry)

        return LapTelemetry(
            driver=str(lap.get("Driver", "")),
            lap_number=int(lap.get("LapNumber")),
            lap_time_seconds=seconds(lap.get("LapTime")),
            team=str(lap.get("Team", "Unknown")),
            compound=str(lap.get("Compound", "Unknown")),
            stint=_optional_int(lap.get("Stint")),
            telemetry=telemetry,
        )

    def _get_lap_row(self, session: Any, driver: str, lap_number: int) -> Any:
        laps = self._driver_laps(session, driver)
        selected = laps[laps["LapNumber"].astype(int) == int(lap_number)]
        if selected.empty:
            raise TelemetryExtractionError(f"No lap {lap_number} found for {driver}.")
        return selected.iloc[0]


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
