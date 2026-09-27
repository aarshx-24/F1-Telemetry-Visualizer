"""Exploratory models with diagnostics and optional held-out scoring."""

from dataclasses import dataclass
import numpy as np
import pandas as pd
from telemetry.analytics.features import DRIVING_FEATURES

TIMING_FEATURES = (
    "LapTimeSeconds",
    "Sector1TimeSeconds",
    "Sector2TimeSeconds",
    "Sector3TimeSeconds",
)


def _matrix(
    table: pd.DataFrame, columns: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    numeric = (
        table[columns]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )
    valid = numeric.notna().all(axis=1)
    return table.loc[valid].copy().reset_index(drop=True), numeric.loc[
        valid
    ].reset_index(drop=True)


@dataclass(frozen=True)
class ClusterResult:
    laps: pd.DataFrame
    diagnostics: pd.DataFrame
    features: tuple[str, ...]
    message: str = ""


class LapClusterAnalyzer:
    def evaluate(
        self,
        lap_table: pd.DataFrame,
        *,
        clusters: int | None = None,
        driving: bool = False,
    ) -> ClusterResult:
        from sklearn.cluster import KMeans
        from sklearn.metrics import adjusted_rand_score, silhouette_score
        from sklearn.preprocessing import StandardScaler

        columns = [
            c
            for c in (DRIVING_FEATURES if driving else (*TIMING_FEATURES, "TyreLife"))
            if c in lap_table
        ]
        if not columns or lap_table.empty:
            return ClusterResult(
                pd.DataFrame(),
                pd.DataFrame(),
                tuple(columns),
                "No complete features available.",
            )
        data, matrix = _matrix(lap_table, columns)
        if len(data) < 6:
            return ClusterResult(
                pd.DataFrame(),
                pd.DataFrame(),
                tuple(columns),
                "At least six complete laps are required.",
            )
        features = StandardScaler().fit_transform(matrix)
        max_k = min(6, len(data) - 1, len(np.unique(features, axis=0)))
        diagnostics, assignments = [], {}
        for k in [clusters] if clusters is not None else range(2, max_k + 1):
            if k is None or k < 2 or k > max_k:
                continue
            labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(
                features
            )
            if len(np.unique(labels)) < 2:
                continue
            score = silhouette_score(
                features, labels, sample_size=min(len(data), 2000), random_state=42
            )
            alternative = KMeans(n_clusters=k, random_state=17, n_init=10).fit_predict(
                features
            )
            diagnostics.append(
                {
                    "Clusters": k,
                    "Silhouette": score,
                    "SeedStabilityARI": adjusted_rand_score(labels, alternative),
                    "Laps": len(data),
                }
            )
            assignments[k] = labels
        if not diagnostics:
            return ClusterResult(
                pd.DataFrame(),
                pd.DataFrame(),
                tuple(columns),
                "Not enough distinct laps for the requested groups.",
            )
        scores = pd.DataFrame(diagnostics).sort_values("Silhouette", ascending=False)
        data["Cluster"] = assignments[int(scores.iloc[0]["Clusters"])].astype(str)
        return ClusterResult(
            data,
            scores,
            tuple(columns),
            "Exploratory groups; silhouette and seed stability are within-session checks.",
        )

    def cluster_laps(
        self, lap_table: pd.DataFrame, *, clusters: int = 3
    ) -> pd.DataFrame:
        return self.evaluate(lap_table, clusters=clusters).laps


class TelemetryAnomalyDetector:
    def detect(
        self, lap_table: pd.DataFrame, *, reference_laps: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        reference = lap_table if reference_laps is None else reference_laps
        columns = [c for c in TIMING_FEATURES if c in lap_table and c in reference]
        if not columns or reference.empty or lap_table.empty:
            return pd.DataFrame()
        _, training = _matrix(reference, columns)
        data, target = _matrix(lap_table, columns)
        if len(training) < 8 or data.empty:
            return pd.DataFrame()
        scaler = StandardScaler().fit(training)
        model = IsolationForest(contamination="auto", random_state=42, n_estimators=150)
        model.fit(scaler.transform(training))
        values = scaler.transform(target)
        data["AnomalyLabel"] = model.predict(values)
        data["AnomalyScore"] = -model.score_samples(values)
        data["IsAnomaly"] = data["AnomalyLabel"].eq(-1)
        # Descriptive cohort deviation, not causal attribution of the forest.
        medians = training.median()
        spread = (training - medians).abs().median() * 1.4826
        spread = spread.where(spread > 1e-9, training.std()).fillna(1).clip(lower=1e-9)
        deviation = (target - medians) / spread
        strongest = deviation.abs().idxmax(axis=1)
        data["LargestDeviationFeature"] = strongest
        data["RobustDeviation"] = [deviation.loc[i, c] for i, c in enumerate(strongest)]
        data["ReferenceScope"] = (
            "Current session"
            if reference_laps is None
            else "Separate reference dataset"
        )
        if {"Driver", "LapNumber", "LapTimeSeconds"}.issubset(data):
            data = data.sort_values(["Driver", "LapNumber"])
            grouped = data.groupby("Driver")["LapTimeSeconds"]
            data["PreviousIncludedLapTime"] = grouped.shift(1)
            data["NextIncludedLapTime"] = grouped.shift(-1)
        return data.sort_values("AnomalyScore", ascending=False).reset_index(drop=True)
