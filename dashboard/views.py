"""Presentation only: analytics and ingestion remain in telemetry packages."""

from __future__ import annotations

from html import escape
import logging

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from telemetry.analytics import (
    BrakingAnalyzer,
    ConsistencyAnalyzer,
    CornerPerformanceAnalyzer,
)
from telemetry.analytics.exploratory import LapClusterAnalyzer, TelemetryAnomalyDetector
from telemetry.analytics.features import driving_features
from telemetry.analytics.tyres import StintTrendAnalyzer
from telemetry.application.sessions import SessionDataset, provenance_table
from telemetry.domain import ComparisonResult, LapTelemetry
from telemetry.processing import DistanceTelemetryAligner
from telemetry.processing.quality import LapQualityFilter, QualityPolicy, QualityResult
from telemetry.visualization import TelemetryPlotFactory

LOG = logging.getLogger(__name__)


class DashboardPlots:
    def __init__(self, dataset: SessionDataset) -> None:
        self.dataset = dataset
        self.figures: list[go.Figure] = []

    def show(self, figure: go.Figure) -> None:
        figure.add_annotation(
            text=escape(self.dataset.source),
            x=0,
            y=-0.24,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 10},
            xanchor="left",
        )
        figure.update_layout(margin={"b": 110})
        self.figures.append(figure)
        st.plotly_chart(figure, width="stretch")

    def report(self) -> str:
        title = escape(f"{self.dataset.request.label} | {self.dataset.source}")
        charts = "".join(
            fig.to_html(full_html=False, include_plotlyjs=True if i == 0 else False)
            for i, fig in enumerate(self.figures)
        )
        return f"<!doctype html><html><head><meta charset='utf-8'><title>Telemetry report</title></head><body><h1>{title}</h1><p>Snapshot: {escape(self.dataset.generated_at)}</p><p>Exploratory analysis, not validated driver-skill or tyre-wear estimates.</p>{charts}</body></html>"


def download(table: pd.DataFrame, name: str, dataset: SessionDataset) -> None:
    st.download_button(
        f"Download {name}",
        provenance_table(table, dataset).to_csv(index=False),
        file_name=f"{name}.csv",
        mime="text/csv",
    )


def quality_controls(table: pd.DataFrame) -> QualityResult:
    with st.expander("Analysis cohort", expanded=False):
        clean = st.checkbox("Exclude pit, deleted and inaccurate laps", True)
        green = st.checkbox("Green-flag laps only", True)
        trim = st.checkbox("Exclude unusually slow laps within each stint", True)
        ratio = (
            st.number_input("Maximum pace ratio", 1.01, 2.0, 1.07, 0.01)
            if trim
            else None
        )
        if "Stint" in table:
            stints = sorted(table["Stint"].dropna().unique().tolist())
            selected = st.multiselect("Stints", stints, default=stints)
            table = table[table["Stint"].isin(selected)]
    result = LapQualityFilter().apply(table, QualityPolicy(clean, green, ratio))
    st.caption(
        f"Analysis cohort: {len(result.accepted)} of {len(result.audit)} laps retained."
    )
    if result.missing_metadata:
        st.caption(
            "Unavailable quality metadata: " + ", ".join(result.missing_metadata)
        )
    return result


def render_tabs(
    dataset: SessionDataset, comparison: ComparisonResult, reference: str
) -> None:
    plotter, charts = TelemetryPlotFactory(), DashboardPlots(dataset)
    laps = list(comparison.laps)
    selected = {lap.driver for lap in laps}
    table = dataset.session.laps
    quality = quality_controls(table[table["Driver"].isin(selected)])
    tabs = st.tabs(["Compare", "Track", "Analytics", "ML", "Data"])
    callbacks = [
        lambda: comparison_view(laps, comparison, reference, plotter, charts),
        lambda: track_view(laps, plotter, charts),
        lambda: analytics_view(dataset, laps, quality.accepted, plotter, charts),
        lambda: ml_view(dataset, quality.accepted, plotter, charts),
        lambda: data_view(dataset, comparison, quality.audit, charts),
    ]
    for tab, render in zip(tabs, callbacks):
        with tab:
            try:
                render()
            except Exception:
                LOG.exception("Analysis view unavailable")
                st.info(
                    "This analysis is unavailable for the current selection. Other views remain available."
                )


def comparison_view(
    laps: list[LapTelemetry],
    comparison: ComparisonResult,
    reference: str,
    plotter: TelemetryPlotFactory,
    charts: DashboardPlots,
) -> None:
    aligned = DistanceTelemetryAligner().align_reference(laps, reference)
    charts.show(plotter.delta_trace(aligned))
    st.caption(
        "Delta is interpolated on shared distance coverage; its endpoint can differ from the official lap-time gap."
    )
    for channel, title in [
        ("Speed", "Speed [km/h]"),
        ("Throttle", "Throttle [%]"),
        ("Brake", "Brake on/off"),
        ("nGear", "Gear"),
        ("RPM", "Engine speed [RPM]"),
        ("DRSActive", "DRS active"),
    ]:
        charts.show(plotter.telemetry_overlay(laps, channel, title=title))
    charts.show(plotter.sector_bars(comparison.sector_table))


def track_view(
    laps: list[LapTelemetry], plotter: TelemetryPlotFactory, charts: DashboardPlots
) -> None:
    charts.show(plotter.track_overlay(laps))
    charts.show(plotter.track_speed_map(laps[0]))
    rows = []
    for lap in laps:
        frame = lap.telemetry
        coordinates = (
            frame.reindex(columns=["X", "Y"])
            .apply(pd.to_numeric, errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
        )
        valid = coordinates.notna().all(axis=1)
        rows.append(
            {
                "Driver": lap.driver,
                "PositionCoveragePercent": float(valid.mean() * 100),
                "Samples": len(frame),
                "PositionSamples": int(valid.sum()),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "Recorded positions are approximate, not centimetre-accurate GPS or an optimal racing line. Missing positions are not reconstructed."
    )


def analytics_view(
    dataset: SessionDataset,
    laps: list[LapTelemetry],
    table: pd.DataFrame,
    plotter: TelemetryPlotFactory,
    charts: DashboardPlots,
) -> None:
    st.subheader("Consistency")
    st.dataframe(
        ConsistencyAnalyzer().summarize(table), hide_index=True, width="stretch"
    )
    st.caption(
        "ConsistencyScore = 100 / (1 + lap-time standard deviation in seconds). A descriptive index, not a validated driver rating; one lap has no score."
    )
    charts.show(plotter.lap_time_scatter(table))
    st.subheader("Stint pace trend")
    fuel = st.number_input(
        "Assumed fuel-related pace gain [s/lap]", 0.0, 0.2, 0.0, 0.005
    )
    trends = StintTrendAnalyzer().summarize(table, fuel_gain_s_per_lap=fuel)
    st.dataframe(trends, hide_index=True, width="stretch")
    charts.show(plotter.tire_degradation(trends))
    st.caption(
        "At least four clean laps per stint. Fuel compensation is a scenario, not measured fuel data. Conditional 95% OLS intervals assume independent residuals; traffic, weather and track evolution remain unmodelled. Qualifying stints rarely support tyre-wear conclusions."
    )
    download(trends, "stint_trends", dataset)
    braking = pd.concat(
        [BrakingAnalyzer().detect_braking_zones(lap) for lap in laps], ignore_index=True
    )
    st.subheader("Braking zones")
    st.dataframe(braking, hide_index=True, width="stretch")
    st.caption(
        "Speed drop per metre is a descriptive proxy, not brake pressure or mechanical braking efficiency."
    )
    corners = pd.concat(
        [
            CornerPerformanceAnalyzer().summarize(
                lap, dataset.session.get_circuit_info()
            )
            for lap in laps
        ],
        ignore_index=True,
    )
    st.subheader("Corner windows")
    st.dataframe(corners, hide_index=True, width="stretch")


def ml_view(
    dataset: SessionDataset,
    table: pd.DataFrame,
    plotter: TelemetryPlotFactory,
    charts: DashboardPlots,
) -> None:
    mode = st.selectbox(
        "Clustering features", ["Timing and tyre life", "Driving telemetry"]
    )
    choice = st.selectbox("Cluster count", ["Automatic", 2, 3, 4, 5, 6])
    features = table
    if mode == "Driving telemetry":
        driving = driving_features(list(dataset.laps))
        if not driving.empty:
            features = table.merge(
                driving, on=["Driver", "LapNumber"], how="inner", validate="one_to_one"
            )
        else:
            features = pd.DataFrame()
    result = LapClusterAnalyzer().evaluate(
        features,
        clusters=None if choice == "Automatic" else choice,
        driving=mode == "Driving telemetry",
    )
    st.caption(result.message)
    if result.features:
        st.caption("Features: " + ", ".join(result.features))
    charts.show(plotter.cluster_scatter(result.laps))
    st.dataframe(result.diagnostics, hide_index=True, width="stretch")
    if not result.laps.empty:
        st.subheader("Cluster profiles (median)")
        st.dataframe(
            result.laps.groupby("Cluster")[list(result.features)].median(),
            width="stretch",
        )
        download(result.laps, "clustered_laps", dataset)
    st.subheader("Unusual laps")
    anomalies = TelemetryAnomalyDetector().detect(table)
    st.dataframe(anomalies, hide_index=True, width="stretch")
    st.caption(
        "Isolation Forest needs eight complete laps. Higher score means more unusual, not an error probability. LargestDeviationFeature is a cohort comparison, not a causal explanation. Models are exploratory and not validated skill scores."
    )
    download(anomalies, "anomaly_scores", dataset)


def data_view(
    dataset: SessionDataset,
    comparison: ComparisonResult,
    audit: pd.DataFrame,
    charts: DashboardPlots,
) -> None:
    st.subheader("Lap inclusion audit")
    st.dataframe(audit, hide_index=True, width="stretch")
    download(audit, "lap_quality_audit", dataset)
    download(dataset.session.laps, "lap_data", dataset)
    download(comparison.sector_table, "sector_data", dataset)
    st.download_button(
        "Download HTML report", charts.report(), "telemetry_report.html", "text/html"
    )
