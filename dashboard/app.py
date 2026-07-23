from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import build_settings
from dashboard.components.sidebar import render_driver_controls, render_request_controls
from dashboard.components.summary import render_lap_metrics
from telemetry.analytics import (
    BrakingAnalyzer,
    ConsistencyAnalyzer,
    CornerPerformanceAnalyzer,
    LapClusterAnalyzer,
    TelemetryAnomalyDetector,
    TireDegradationAnalyzer,
)
from telemetry.comparison import DriverComparisonService
from telemetry.domain import SessionRequest
from telemetry.ingestion import FastF1DataLoadError, FastF1SessionLoader
from telemetry.ingestion.demo_data import DemoTelemetryFactory
from telemetry.processing import TelemetryExtractor
from telemetry.visualization import TelemetryPlotFactory


FALLBACK_DRIVER_OPTIONS = [
    "VER", "PER", "LEC", "SAI", "HAM", "RUS", "NOR", "PIA",
    "ALO", "STR", "GAS", "OCO", "ALB", "SAR", "TSU", "RIC",
    "LAW", "BOT", "ZHO", "HUL", "MAG",
]

st.set_page_config(
    page_title="F1 Telemetry Visualizer",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {background: #111827; border: 1px solid #243244; padding: 0.8rem; border-radius: 8px;}
    [data-testid="stSidebar"] {background: #0b1220;}
    h1, h2, h3 {letter-spacing: 0;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def load_session(request: SessionRequest, telemetry: bool) -> Any:
    settings = build_settings(ROOT)
    loader = FastF1SessionLoader(settings=settings)
    return loader.load_session(request, telemetry=telemetry)


@st.cache_data(show_spinner=False)
def load_grand_prix_options(year: int) -> list[str]:
    settings = build_settings(ROOT)
    loader = FastF1SessionLoader(settings=settings)
    return loader.list_grand_prix(year)


def main() -> None:
    st.title("F1 Telemetry Visualizer")

    st.sidebar.header("Session")
    selected_year = int(st.sidebar.number_input("Year", min_value=2018, max_value=2026, value=2024))
    grand_prix_options = load_grand_prix_options(selected_year)
    request, frequency_hz = render_request_controls(grand_prix_options, selected_year)
    if st.sidebar.button("Clear session cache"):
        load_session.clear()
        load_grand_prix_options.clear()
        st.session_state["load_telemetry_charts"] = False
        st.rerun()

    extractor = TelemetryExtractor()
    timing_session = _safe_load_session(request, telemetry=False, show_error=False)
    timing_lap_table = pd.DataFrame()

    if timing_session is None:
        drivers = FALLBACK_DRIVER_OPTIONS
        st.warning(
            "FastF1 timing data could not be loaded yet, so fallback driver options are shown. "
            "You can still choose drivers and retry telemetry loading."
        )
    else:
        try:
            drivers = extractor.available_drivers(timing_session)
            timing_lap_table = extractor.lap_table(timing_session)
        except Exception as exc:
            drivers = FALLBACK_DRIVER_OPTIONS
            st.warning("Driver metadata could not be read from FastF1, so fallback driver options are shown.")
            st.caption(str(exc))

    controls = render_driver_controls(request, frequency_hz, drivers)

    selected_drivers = controls.selected_drivers or drivers[:2]
    if len(selected_drivers) < 2:
        st.info("Select at least two drivers.")
        return

    request_key = (
        f"{request.year}-{request.grand_prix}-{request.session_type}-"
        f"{'-'.join(selected_drivers)}-{controls.frequency_hz}"
    )
    if st.session_state.get("telemetry_request_key") != request_key:
        st.session_state["telemetry_request_key"] = request_key
        st.session_state["load_telemetry_charts"] = False

    if st.sidebar.button("Load telemetry charts", type="primary"):
        st.session_state["load_telemetry_charts"] = True

    st.info("Drivers loaded. Click 'Load telemetry charts' to fetch full FastF1 telemetry.")

    if not st.session_state.get("load_telemetry_charts", False):
        if not timing_lap_table.empty:
            st.subheader("Lap Data Preview")
            st.dataframe(timing_lap_table, use_container_width=True, hide_index=True)
        else:
            st.info(
                "Timing data is not available yet. Use Clear session cache, then click "
                "Load telemetry charts to retry."
            )
        return

    plotter = TelemetryPlotFactory()
    session = _safe_load_session(request, telemetry=True)
    if session is None:
        st.warning(
            "Live FastF1 telemetry is unavailable right now. Showing built-in demo telemetry "
            "so the dashboard remains usable online."
        )
        demo_factory = DemoTelemetryFactory()
        comparison = demo_factory.build_comparison(controls.request, selected_drivers)
        demo_session = demo_factory.build_session(selected_drivers)
        laps = list(comparison.laps)
        lap_table = demo_session.laps
        render_lap_metrics(laps)
        _render_analysis_tabs(demo_session, extractor, laps, lap_table, plotter, comparison)
        return

    comparison_service = DriverComparisonService(extractor=extractor)

    try:
        comparison = comparison_service.compare_fastest_laps(
            session,
            controls.request,
            selected_drivers,
            frequency=controls.frequency_hz,
        )
    except Exception as exc:
        st.error(f"Could not build driver comparison: {exc}")
        return

    laps = list(comparison.laps)
    lap_table = extractor.lap_table(session)
    render_lap_metrics(laps)

    _render_analysis_tabs(session, extractor, laps, lap_table, plotter, comparison)


def _render_analysis_tabs(
    session: Any,
    extractor: TelemetryExtractor,
    laps: list[Any],
    lap_table: pd.DataFrame,
    plotter: TelemetryPlotFactory,
    comparison: Any,
) -> None:
    tabs = st.tabs(["Compare", "Track", "Analytics", "ML", "Data"])

    with tabs[0]:
        _render_compare_tab(plotter, comparison, laps)

    with tabs[1]:
        _render_track_tab(plotter, laps)

    with tabs[2]:
        _render_analytics_tab(session, extractor, laps, lap_table, plotter)

    with tabs[3]:
        _render_ml_tab(lap_table, plotter)

    with tabs[4]:
        _render_data_tab(lap_table, comparison.sector_table)

def _safe_load_session(
    request: SessionRequest,
    *,
    telemetry: bool,
    show_error: bool = True,
) -> Any | None:
    load_type = "telemetry" if telemetry else "timing"
    with st.spinner(f"Loading {load_type} data for {request.label}"):
        try:
            return load_session(request, telemetry)
        except FastF1DataLoadError as exc:
            if show_error:
                st.error(str(exc))
                st.info("Use the sidebar button 'Clear session cache', then try again.")
            return None
        except Exception as exc:
            if show_error:
                st.error(f"Session load failed: {exc}")
            return None


def _render_compare_tab(
    plotter: TelemetryPlotFactory,
    comparison: Any,
    laps: list[Any],
) -> None:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            plotter.telemetry_overlay(laps, "Speed", title="Speed comparison"),
            use_container_width=True,
        )
        st.plotly_chart(
            plotter.telemetry_overlay(laps, "Throttle", title="Throttle comparison"),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(plotter.delta_trace(comparison.aligned), use_container_width=True)
        st.plotly_chart(
            plotter.telemetry_overlay(laps, "Brake", title="Brake comparison"),
            use_container_width=True,
        )

    gear, rpm = st.columns(2)
    with gear:
        st.plotly_chart(
            plotter.telemetry_overlay(laps, "nGear", title="Gear comparison"),
            use_container_width=True,
        )
    with rpm:
        st.plotly_chart(
            plotter.telemetry_overlay(laps, "RPM", title="RPM comparison"),
            use_container_width=True,
        )

    st.plotly_chart(plotter.sector_bars(comparison.sector_table), use_container_width=True)
    if comparison.insights:
        st.subheader("Insights")
        for insight in comparison.insights:
            st.write(f"- {insight}")


def _render_track_tab(plotter: TelemetryPlotFactory, laps: list[Any]) -> None:
    heatmap, overlay = st.columns(2)
    with heatmap:
        st.plotly_chart(plotter.track_speed_map(laps[0]), use_container_width=True)
    with overlay:
        st.plotly_chart(plotter.track_overlay(laps), use_container_width=True)


def _render_analytics_tab(
    session: Any,
    extractor: TelemetryExtractor,
    laps: list[Any],
    lap_table: pd.DataFrame,
    plotter: TelemetryPlotFactory,
) -> None:
    consistency = ConsistencyAnalyzer().summarize(lap_table)
    tire_degradation = TireDegradationAnalyzer().summarize(lap_table)

    first, second = st.columns(2)
    with first:
        st.subheader("Consistency")
        st.dataframe(consistency, use_container_width=True, hide_index=True)
    with second:
        st.subheader("Tyre Degradation")
        st.dataframe(tire_degradation, use_container_width=True, hide_index=True)

    st.plotly_chart(plotter.lap_time_scatter(lap_table), use_container_width=True)
    st.plotly_chart(plotter.tire_degradation(tire_degradation), use_container_width=True)

    braking_rows = [BrakingAnalyzer().detect_braking_zones(lap) for lap in laps]
    braking = pd.concat(braking_rows, ignore_index=True) if braking_rows else pd.DataFrame()
    st.subheader("Braking Zones")
    st.dataframe(braking, use_container_width=True, hide_index=True)

    circuit_info = session.get_circuit_info()
    corner_rows = [
        CornerPerformanceAnalyzer().summarize(lap, circuit_info)
        for lap in laps
    ]
    corner_table = pd.concat(corner_rows, ignore_index=True) if corner_rows else pd.DataFrame()
    st.subheader("Corner Performance")
    st.dataframe(corner_table, use_container_width=True, hide_index=True)


def _render_ml_tab(lap_table: pd.DataFrame, plotter: TelemetryPlotFactory) -> None:
    clusters = LapClusterAnalyzer().cluster_laps(lap_table)
    anomalies = TelemetryAnomalyDetector().detect(lap_table)

    st.plotly_chart(plotter.cluster_scatter(clusters), use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Clustered Laps")
        st.dataframe(clusters, use_container_width=True, hide_index=True)
    with right:
        st.subheader("Anomaly Detection")
        st.dataframe(anomalies, use_container_width=True, hide_index=True)


def _render_data_tab(lap_table: pd.DataFrame, sector_table: pd.DataFrame) -> None:
    st.subheader("Lap Data")
    st.dataframe(lap_table, use_container_width=True, hide_index=True)
    st.download_button(
        label="Download lap data CSV",
        data=lap_table.to_csv(index=False),
        file_name="lap_data.csv",
        mime="text/csv",
    )

    st.subheader("Sector Data")
    st.dataframe(sector_table, use_container_width=True, hide_index=True)
    st.download_button(
        label="Download sector data CSV",
        data=sector_table.to_csv(index=False),
        file_name="sector_data.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
