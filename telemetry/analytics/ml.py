from __future__ import annotations

import pandas as pd


class LapClusterAnalyzer:
    """Cluster laps using lightweight timing features."""

    def cluster_laps(self, lap_table: pd.DataFrame, *, clusters: int = 3) -> pd.DataFrame:
        if lap_table.empty:
            return pd.DataFrame()

        feature_columns = [
            column
            for column in (
                "LapTimeSeconds",
                "Sector1TimeSeconds",
                "Sector2TimeSeconds",
                "Sector3TimeSeconds",
                "TyreLife",
            )
            if column in lap_table.columns
        ]
        data = lap_table.dropna(subset=feature_columns).copy()
        if len(data) < max(2, clusters) or not feature_columns:
            return pd.DataFrame()

        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        k = min(clusters, len(data))
        features = StandardScaler().fit_transform(data[feature_columns])
        model = KMeans(n_clusters=k, random_state=42, n_init="auto")
        data["Cluster"] = model.fit_predict(features)
        return data.reset_index(drop=True)


class TelemetryAnomalyDetector:
    """Find unusual laps from timing-sector features."""

    def detect(self, lap_table: pd.DataFrame) -> pd.DataFrame:
        if lap_table.empty:
            return pd.DataFrame()

        feature_columns = [
            column
            for column in (
                "LapTimeSeconds",
                "Sector1TimeSeconds",
                "Sector2TimeSeconds",
                "Sector3TimeSeconds",
            )
            if column in lap_table.columns
        ]
        data = lap_table.dropna(subset=feature_columns).copy()
        if len(data) < 8 or not feature_columns:
            return pd.DataFrame()

        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        features = StandardScaler().fit_transform(data[feature_columns])
        detector = IsolationForest(contamination="auto", random_state=42)
        data["AnomalyScore"] = detector.fit_predict(features)
        data["IsAnomaly"] = data["AnomalyScore"] == -1
        return data.sort_values("IsAnomaly", ascending=False).reset_index(drop=True)
