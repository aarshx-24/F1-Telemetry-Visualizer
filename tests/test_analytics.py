import pandas as pd

from telemetry.analytics import ConsistencyAnalyzer, TireDegradationAnalyzer


def test_consistency_analyzer_summarizes_driver_pace() -> None:
    laps = pd.DataFrame(
        {
            "Driver": ["AAA", "AAA", "BBB", "BBB"],
            "LapTimeSeconds": [80.0, 81.0, 82.0, 84.0],
        }
    )

    result = ConsistencyAnalyzer().summarize(laps)

    assert result.iloc[0]["Driver"] == "AAA"
    assert result.iloc[0]["BestLap"] == 80.0


def test_tire_degradation_requires_stint_trend() -> None:
    laps = pd.DataFrame(
        {
            "Driver": ["AAA", "AAA", "AAA"],
            "LapNumber": [1, 2, 3],
            "LapTimeSeconds": [80.0, 81.0, 82.0],
            "Stint": [1, 1, 1],
            "Compound": ["MEDIUM", "MEDIUM", "MEDIUM"],
        }
    )

    result = TireDegradationAnalyzer().summarize(laps)

    assert round(result.iloc[0]["DegradationPerLap"], 6) == 1.0
