from __future__ import annotations

import logging
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from config.settings import build_settings
from dashboard.components.summary import render_lap_metrics
from dashboard.views import render_tabs
from telemetry.application.sessions import SessionDataset, SessionService
from telemetry.domain import SessionRequest
from telemetry.ingestion.demo_data import DemoTelemetryFactory
from telemetry.ingestion.processed_store import ProcessedSession
from telemetry.ingestion.calendar import COMMON_GRAND_PRIX_NAMES

LOG = logging.getLogger(__name__)
st.set_page_config(page_title="F1 Telemetry Visualizer", layout="wide")


@st.cache_resource
def service() -> SessionService:
    return SessionService(build_settings(ROOT))


def session_controls() -> SessionRequest:
    catalog = service().catalog()
    selection = st.sidebar.selectbox(
        "Session source", ["Saved sessions", "Fetch another session"]
    )
    if selection == "Saved sessions" and catalog:
        return st.sidebar.selectbox(
            "Available session", catalog, format_func=lambda item: item.label
        )
    from datetime import date

    year = int(st.sidebar.number_input("Year", 2018, date.today().year, 2024))
    # The static list remains usable when the schedule endpoint is unavailable.
    options = sorted(set(COMMON_GRAND_PRIX_NAMES))
    if st.sidebar.button("Refresh Grand Prix calendar"):
        try:
            names = service().client.calendar(year)
            if names:
                st.session_state[f"calendar_{year}"] = names
        except Exception:
            LOG.exception("Calendar refresh unavailable")
    options = st.session_state.get(f"calendar_{year}", options)
    gp = st.sidebar.selectbox("Grand Prix", options)
    kind = st.sidebar.selectbox("Session", ["Q", "R", "SQ", "S", "FP1", "FP2", "FP3"])
    return SessionRequest(year, gp, kind)


def main() -> None:
    st.title("F1 Telemetry Visualizer")
    mode = st.sidebar.radio("Data mode", ["Real sessions", "Demonstration"])
    if mode == "Demonstration":
        selected = st.sidebar.multiselect(
            "Drivers", ["VER", "LEC", "HAM", "NOR"], ["VER", "LEC"], max_selections=4
        )
        if len(selected) < 2:
            st.info("Select at least two drivers.")
            return
        request = SessionRequest(2024, "Synthetic circuit", "DEMO")
        factory = DemoTelemetryFactory()
        comparison = factory.build_comparison(request, selected)
        demo_session = factory.build_session(selected)
        dataset = SessionDataset(
            request,
            ProcessedSession(
                demo_session.laps, demo_session.get_circuit_info().corners
            ),
            comparison.laps,
            "SYNTHETIC DEMONSTRATION - not race data",
            "synthetic",
        )
    else:
        request = session_controls()
        refresh = st.sidebar.button("Refresh from FastF1")
        with st.spinner("Opening session data..."):
            dataset = service().open(request, refresh=refresh)
        if dataset is None:
            st.info(
                "The requested session has not loaded. No synthetic data has been substituted."
            )
            st.caption(service().client.failure_message(request))
            return
        defaults = [driver for driver in ("VER", "LEC") if driver in dataset.drivers]
        selected = st.sidebar.multiselect(
            "Drivers",
            dataset.drivers,
            defaults or dataset.drivers[:2],
            max_selections=4,
        )
        if len(selected) < 2:
            st.info("Select at least two drivers.")
            return
        selections = {}
        include_online = st.sidebar.checkbox(
            "Include laps requiring an online download",
            value=False,
            key=f"online_laps_{request.label}",
        )
        if include_online:
            st.sidebar.caption(
                "These laps have timing records but no saved telemetry. Availability depends on the FastF1 connection."
            )
        for driver in selected:
            saved = [lap for lap in dataset.laps if lap.driver == driver]
            fastest = min(saved, key=lambda lap: lap.lap_time_seconds).lap_number
            table = dataset.session.laps
            rows = table[table["Driver"].eq(driver)].dropna(
                subset=["LapNumber", "LapTimeSeconds"]
            )
            saved_numbers = {lap.lap_number for lap in saved}
            numbers = (
                sorted(saved_numbers | set(rows["LapNumber"].astype(int)))
                if include_online
                else sorted(saved_numbers)
            )
            st.sidebar.caption(
                f"{driver}: telemetry saved for {len(saved_numbers)} laps."
            )
            selection_key = f"lap_{request.label}_{driver}_{include_online}"
            if st.session_state.get(selection_key, fastest) not in numbers:
                st.session_state[selection_key] = fastest
            selections[driver] = st.sidebar.selectbox(
                f"{driver} lap",
                numbers,
                index=numbers.index(fastest),
                format_func=lambda number, stored=saved_numbers: (
                    f"Lap {number}"
                    + (
                        " (saved)"
                        if number in stored
                        else " (requires online download)"
                    )
                ),
                key=selection_key,
            )
        with st.spinner("Opening selected laps..."):
            comparison = service().compare(dataset, selections)
        if comparison is None:
            st.info(
                "The selected lap could not be retrieved. Turn off 'Include laps requiring an online download' to return to saved telemetry. No other lap has been substituted."
            )
            st.caption(service().client.failure_message(request, selections))
            return
        if any(
            not any(
                saved.driver == lap.driver and saved.lap_number == lap.lap_number
                for saved in dataset.laps
            )
            for lap in comparison.laps
        ):
            refreshed = service().open(request)
            if refreshed is not None:
                dataset = replace(refreshed, source="Downloaded FastF1 archive")
    st.caption(f"{dataset.source} | {request.label} | Snapshot: {dataset.generated_at}")
    reference = st.sidebar.selectbox("Reference driver", selected)
    render_lap_metrics(list(comparison.laps))
    render_tabs(dataset, comparison, reference)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOG.exception("Dashboard request could not be completed")
        st.info(
            "This view is temporarily unavailable. Choose a saved session or retry later. Technical details have been recorded in the server logs."
        )
