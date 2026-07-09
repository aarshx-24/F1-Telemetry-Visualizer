import pandas as pd

from telemetry.domain import LapTelemetry
from telemetry.processing import DistanceTelemetryAligner, TelemetryCleaner


def test_cleaner_adds_seconds_and_binary_channels() -> None:
    raw = pd.DataFrame(
        {
            "Distance": [10, 0, 20],
            "Time": pd.to_timedelta([1, 0, 2], unit="s"),
            "SessionTime": pd.to_timedelta([101, 100, 102], unit="s"),
            "Speed": [200, 180, 210],
            "Brake": [False, True, False],
            "DRS": [0, 12, 14],
        }
    )

    cleaned = TelemetryCleaner().prepare_lap_telemetry(raw)

    assert cleaned["Distance"].tolist() == [0, 10, 20]
    assert "TimeSeconds" in cleaned
    assert "SessionTimeSeconds" in cleaned
    assert cleaned["Brake"].tolist() == [1, 0, 0]
    assert cleaned["DRSActive"].tolist() == [1, 0, 1]


def test_distance_aligner_computes_delta_seconds() -> None:
    ref = LapTelemetry(
        driver="AAA",
        lap_number=1,
        lap_time_seconds=80.0,
        team="Team",
        compound="SOFT",
        stint=1,
        telemetry=pd.DataFrame(
            {
                "Distance": [0, 50, 100],
                "TimeSeconds": [0, 10, 20],
                "Speed": [100, 150, 200],
            }
        ),
    )
    cmp = LapTelemetry(
        driver="BBB",
        lap_number=1,
        lap_time_seconds=82.0,
        team="Team",
        compound="SOFT",
        stint=1,
        telemetry=pd.DataFrame(
            {
                "Distance": [0, 50, 100],
                "TimeSeconds": [0, 11, 22],
                "Speed": [100, 145, 190],
            }
        ),
    )

    aligned = DistanceTelemetryAligner().align_pair(ref, cmp, samples=3)

    assert aligned["DeltaSeconds"].tolist() == [0.0, 1.0, 2.0]
