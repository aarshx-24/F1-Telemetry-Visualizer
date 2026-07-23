from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from telemetry.analytics.insights import DriverInsightEngine
from telemetry.domain import ComparisonResult, LapTelemetry, SessionRequest
from telemetry.processing import DistanceTelemetryAligner


@dataclass(frozen=True, slots=True)
class DemoSession:
    """Small session-like object used when FastF1 data is unavailable."""

    laps: pd.DataFrame

    def get_circuit_info(self) -> object:
        corners = pd.DataFrame(
            {
                "Number": list(range(1, 9)),
                "Letter": [""] * 8,
                "Distance": [420, 980, 1450, 1980, 2610, 3350, 4210, 4820],
            }
        )
        return type("DemoCircuitInfo", (), {"corners": corners})()


class DemoTelemetryFactory:
    """Create deterministic telemetry so the dashboard always has a usable demo."""

    def build_comparison(
        self,
        request: SessionRequest,
        drivers: list[str],
    ) -> ComparisonResult:
        selected = drivers[:2] if len(drivers) >= 2 else ["VER", "LEC"]
        laps = [self._build_lap(driver, index) for index, driver in enumerate(selected)]
        aligned = DistanceTelemetryAligner().align_pair(laps[0], laps[1])
        sector_table = self._sector_table(laps)
        insights = DriverInsightEngine().build_driver_comparison_insights(laps, aligned)
        return ComparisonResult(
            request=request,
            laps=tuple(laps),
            aligned=aligned,
            sector_table=sector_table,
            insights=tuple(insights),
        )

    def build_session(self, drivers: list[str]) -> DemoSession:
        rows: list[dict[str, object]] = []
        selected = drivers[:6] if drivers else ["VER", "LEC", "HAM", "NOR", "ALO", "SAI"]
        for driver_index, driver in enumerate(selected):
            base = 91.2 + driver_index * 0.28
            for lap_number in range(1, 13):
                tyre_penalty = max(0, lap_number - 3) * 0.055
                traffic = 0.18 * np.sin(lap_number * 0.9 + driver_index)
                lap_time = base + tyre_penalty + traffic
                rows.append(
                    {
                        "Driver": driver,
                        "LapNumber": lap_number,
                        "LapTimeSeconds": lap_time,
                        "Sector1TimeSeconds": lap_time * 0.315,
                        "Sector2TimeSeconds": lap_time * 0.365,
                        "Sector3TimeSeconds": lap_time * 0.320,
                        "Compound": "SOFT" if lap_number <= 6 else "MEDIUM",
                        "TyreLife": lap_number,
                        "Stint": 1 if lap_number <= 6 else 2,
                        "Team": _team_for_driver(driver),
                        "TrackStatus": "1",
                    }
                )
        return DemoSession(laps=pd.DataFrame(rows))

    def _build_lap(self, driver: str, index: int) -> LapTelemetry:
        distance = np.linspace(0, 5412, 900)
        progress = distance / distance.max()
        corner_profile = np.zeros_like(distance)
        for corner_distance, severity in (
            (420, 58), (980, 92), (1450, 44), (1980, 72),
            (2610, 64), (3350, 88), (4210, 52), (4820, 78),
        ):
            corner_profile += severity * np.exp(-((distance - corner_distance) / 125) ** 2)

        driver_offset = index * 0.9
        speed = 318 - corner_profile + 7 * np.sin(progress * 7 * np.pi + driver_offset)
        speed = np.clip(speed + index * 2.5, 72, 336)
        brake = (corner_profile > 36).astype(float)
        throttle = np.clip(100 - corner_profile * 1.15 + 8 * np.cos(progress * 8 * np.pi), 0, 100)
        rpm = 8200 + speed * 34 + 650 * np.sin(progress * 20 * np.pi)
        gear = np.clip(np.floor((speed - 45) / 38), 1, 8)
        drs = ((distance > 620) & (distance < 1160)) | ((distance > 3850) & (distance < 4610))
        time_seconds = np.cumsum(np.gradient(distance) / np.maximum(speed / 3.6, 1))
        time_seconds *= (91.4 + index * 0.32) / time_seconds[-1]
        angle = 2 * np.pi * progress
        radius = 900 + 180 * np.sin(3 * angle)
        x = radius * np.cos(angle) + 95 * np.sin(5 * angle)
        y = 0.62 * radius * np.sin(angle) + 75 * np.cos(4 * angle)

        telemetry = pd.DataFrame(
            {
                "Distance": distance,
                "TimeSeconds": time_seconds,
                "Speed": speed,
                "Throttle": throttle,
                "Brake": brake,
                "nGear": gear,
                "RPM": rpm,
                "DRS": drs.astype(int),
                "X": x + index * 18,
                "Y": y - index * 12,
            }
        )
        return LapTelemetry(
            driver=driver,
            lap_number=8 + index,
            lap_time_seconds=float(time_seconds[-1]),
            team=_team_for_driver(driver),
            compound="SOFT",
            stint=1,
            telemetry=telemetry,
        )

    @staticmethod
    def _sector_table(laps: list[LapTelemetry]) -> pd.DataFrame:
        rows = []
        for lap in laps:
            rows.append(
                {
                    "Driver": lap.driver,
                    "Lap": lap.lap_number,
                    "LapTime": lap.lap_time_seconds,
                    "Sector1": lap.lap_time_seconds * 0.315,
                    "Sector2": lap.lap_time_seconds * 0.365,
                    "Sector3": lap.lap_time_seconds * 0.320,
                    "Compound": lap.compound,
                    "Team": lap.team,
                }
            )
        return pd.DataFrame(rows)


def _team_for_driver(driver: str) -> str:
    return {
        "VER": "Red Bull Racing",
        "PER": "Red Bull Racing",
        "LEC": "Ferrari",
        "SAI": "Ferrari",
        "HAM": "Mercedes",
        "RUS": "Mercedes",
        "NOR": "McLaren",
        "PIA": "McLaren",
        "ALO": "Aston Martin",
        "STR": "Aston Martin",
    }.get(driver, "Demo Team")
