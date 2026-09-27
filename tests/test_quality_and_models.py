import numpy as np
import pandas as pd
import pytest

from telemetry.analytics.evaluation import evaluate_held_out
from telemetry.analytics.exploratory import LapClusterAnalyzer, TelemetryAnomalyDetector
from telemetry.analytics.insights import ConsistencyAnalyzer
from telemetry.analytics.tyres import StintTrendAnalyzer
from telemetry.domain import SessionRequest
from telemetry.ingestion.demo_data import DemoTelemetryFactory
from telemetry.processing import DistanceTelemetryAligner
from telemetry.processing.quality import LapQualityFilter, QualityPolicy
from telemetry.visualization.plotly_factory import TelemetryPlotFactory, DRIVER_COLORS


def cohort():
    return DemoTelemetryFactory().build_session(["VER", "LEC"]).laps


def test_quality_audit_excludes_known_bad_laps_without_mutating_input():
    data = cohort()
    data["Deleted"] = False
    data["IsAccurate"] = True
    data["PitInTime"] = None
    data["PitOutTime"] = None
    data.loc[0, "Deleted"] = True
    data.loc[1, "IsAccurate"] = False
    data.loc[2, "PitInTime"] = "00:20:00"
    data.loc[3, "TrackStatus"] = "12"
    data.loc[4, "LapTimeSeconds"] = 300
    result = LapQualityFilter().apply(data)
    assert not result.audit.loc[:4, "Included"].any()
    assert len(result.accepted) == len(data) - 5
    assert "Included" not in data
    assert not result.missing_metadata


def test_quality_reports_missing_flags_and_rejects_nonfinite_times():
    data = cohort()
    data.loc[0, "LapTimeSeconds"] = np.inf
    result = LapQualityFilter().apply(data)
    assert "Deleted" in result.missing_metadata
    assert not result.audit.iloc[0]["Included"]


def test_consistency_one_lap_is_not_perfect_score():
    assert pd.isna(
        ConsistencyAnalyzer().summarize(cohort().iloc[:1]).iloc[0]["ConsistencyScore"]
    )


def test_stint_slope_and_fuel_scenario():
    data = cohort().iloc[:6].copy()
    data["LapTimeSeconds"] = 90 + 0.1 * data["LapNumber"]
    result = StintTrendAnalyzer().summarize(data, fuel_gain_s_per_lap=0.03).iloc[0]
    assert result["DegradationPerLap"] == pytest.approx(0.13)
    assert result["RawTrend"] == pytest.approx(0.1)
    assert result["Lower95"] <= result["DegradationPerLap"] <= result["Upper95"]
    assert StintTrendAnalyzer().summarize(data.iloc[:3]).empty


def test_reference_delta_supports_three_drivers_and_discrete_channels():
    laps = list(
        DemoTelemetryFactory()
        .build_comparison(SessionRequest(2024, "Test", "Q"), ["VER", "LEC", "HAM"])
        .laps
    )
    result = DistanceTelemetryAligner().align_reference(laps, "LEC")
    assert {"Delta_VER", "Delta_HAM"}.issubset(result)
    assert "Delta_LEC" not in result
    assert result.iloc[-1]["Delta_VER"] == pytest.approx(-0.32)
    assert set(result["VER_Brake"].unique()) <= {0, 1}
    assert set(result["VER_DRSActive"].unique()) <= {0, 1}


def test_interpolation_sorts_samples():
    frame = pd.DataFrame({"Distance": [20, 0, 10], "Brake": [0, 0, 1]})
    values = DistanceTelemetryAligner._interpolate(
        frame, "Brake", np.array([0, 5, 10, 15, 20])
    )
    assert values.tolist() == [0, 0, 1, 1, 0]


def test_delta_colors_match_driver_order_with_nonfirst_reference():
    laps = list(
        DemoTelemetryFactory()
        .build_comparison(SessionRequest(2024, "Test", "Q"), ["VER", "LEC", "HAM"])
        .laps
    )
    aligned = DistanceTelemetryAligner().align_reference(laps, "LEC")
    figure = TelemetryPlotFactory().delta_trace(aligned)
    assert [trace.name for trace in figure.data] == ["VER", "HAM"]
    assert [trace.line.color for trace in figure.data] == [
        DRIVER_COLORS[0],
        DRIVER_COLORS[2],
    ]


def test_clustering_has_diagnostics_and_handles_degenerate_data():
    result = LapClusterAnalyzer().evaluate(cohort())
    assert not result.laps.empty
    assert result.diagnostics["Silhouette"].between(-1, 1).all()
    assert result.diagnostics["SeedStabilityARI"].between(-1, 1).all()
    constant = pd.concat([cohort().iloc[:1]] * 8, ignore_index=True)
    assert LapClusterAnalyzer().evaluate(constant).laps.empty
    assert LapClusterAnalyzer().evaluate(cohort().iloc[:3]).laps.empty


def test_anomaly_scores_are_continuous_with_separate_reference():
    target = cohort().iloc[:4].copy()
    target.loc[0, "LapTimeSeconds"] = 180
    result = TelemetryAnomalyDetector().detect(target, reference_laps=cohort())
    assert result["AnomalyScore"].between(0, 1).all()
    assert set(result["AnomalyLabel"]) <= {-1, 1}
    assert result["ReferenceScope"].eq("Separate reference dataset").all()
    assert "LargestDeviationFeature" in result
    assert TelemetryAnomalyDetector().detect(cohort().iloc[:4]).empty


def test_held_out_validation_rejects_same_session_and_demo():
    reference = cohort().assign(
        Session="2023 Test Q", DataSource="Prepared FastF1 archive"
    )
    with pytest.raises(ValueError, match="distinct"):
        evaluate_held_out(reference, reference)
    target = reference.assign(Session="2024 Test Q")
    scores, metrics = evaluate_held_out(reference, target)
    assert len(scores) == len(target)
    assert "ROCAUC" not in metrics
    with pytest.raises(ValueError, match="Synthetic"):
        evaluate_held_out(
            reference, target.assign(DataSource="SYNTHETIC DEMONSTRATION")
        )
