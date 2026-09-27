"""Evaluate anomaly scoring against a distinct reference-session cohort."""

import pandas as pd
from telemetry.analytics.exploratory import TelemetryAnomalyDetector
from telemetry.processing.quality import LapQualityFilter, QualityPolicy


def evaluate_held_out(
    reference: pd.DataFrame, target: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not {"Session", "DataSource"}.issubset(reference) or not {
        "Session",
        "DataSource",
    }.issubset(target):
        raise ValueError("Use exported CSVs with Session and DataSource provenance.")
    if set(reference["Session"].dropna()) & set(target["Session"].dropna()):
        raise ValueError("Reference and evaluation sessions must be distinct.")
    if (
        reference["DataSource"].str.contains("synthetic|demo", case=False).any()
        or target["DataSource"].str.contains("synthetic|demo", case=False).any()
    ):
        raise ValueError(
            "Synthetic demonstrations cannot validate real-session models."
        )
    policy = QualityPolicy(pace_ratio=None)
    training = LapQualityFilter().apply(reference, policy).accepted
    testing = LapQualityFilter().apply(target, policy).accepted
    scores = TelemetryAnomalyDetector().detect(testing, reference_laps=training)
    if scores.empty:
        raise ValueError("Insufficient complete clean laps for held-out scoring.")
    metrics = {
        "ReferenceLaps": len(training),
        "EvaluationLaps": len(scores),
        "FlaggedFraction": float(scores["IsAnomaly"].mean()),
        "MedianAnomalyScore": float(scores["AnomalyScore"].median()),
    }
    if "KnownAnomaly" in scores and scores["KnownAnomaly"].notna().all():
        labels = pd.to_numeric(scores["KnownAnomaly"], errors="raise")
        if not labels.isin([0, 1]).all():
            raise ValueError("KnownAnomaly must contain zero or one.")
        from sklearn.metrics import precision_score, recall_score, roc_auc_score

        metrics["Precision"] = precision_score(
            labels, scores["IsAnomaly"], zero_division=0
        )
        metrics["Recall"] = recall_score(labels, scores["IsAnomaly"], zero_division=0)
        if labels.nunique() == 2:
            metrics["ROCAUC"] = roc_auc_score(labels, scores["AnomalyScore"])
    return scores, pd.DataFrame([metrics])
