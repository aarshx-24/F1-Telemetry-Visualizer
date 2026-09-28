from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from telemetry.domain import SessionRequest
from telemetry.ingestion import preferred_grand_prix_index


@dataclass(frozen=True, slots=True)
class DashboardControls:
    request: SessionRequest
    frequency_hz: int
    selected_drivers: list[str]


def render_request_controls(
    grand_prix_options: list[str],
    year: int,
) -> tuple[SessionRequest, int]:
    grand_prix = st.sidebar.selectbox(
        "Grand Prix",
        options=grand_prix_options,
        index=preferred_grand_prix_index(grand_prix_options),
        key=f"grand_prix_{year}",
    )
    session_type = st.sidebar.selectbox(
        "Session",
        options=["Q", "R", "SQ", "S", "FP1", "FP2", "FP3"],
        index=0,
        key=f"session_{year}_{grand_prix}",
    )
    frequency_hz = int(st.sidebar.slider("Telemetry frequency", 5, 20, 10, step=1))

    return (
        SessionRequest(
            year=year,
            grand_prix=grand_prix,
            session_type=session_type,
        ),
        frequency_hz,
    )


def render_driver_controls(
    request: SessionRequest,
    frequency_hz: int,
    available_drivers: list[str],
    *,
    unavailable: bool = False,
) -> DashboardControls:
    drivers = available_drivers
    default_drivers = _default_drivers(drivers)
    selected_drivers = st.sidebar.multiselect(
        "Drivers",
        options=drivers,
        default=default_drivers,
        disabled=unavailable or not drivers,
        key=f"drivers_{request.year}_{request.grand_prix}_{request.session_type}_{unavailable}",
    )
    if unavailable or not drivers:
        st.sidebar.caption(
            "Driver selection is unavailable because this session's driver data did not load."
        )
    if len(selected_drivers) > 4:
        selected_drivers = selected_drivers[:4]
        st.sidebar.warning("Using the first four selected drivers.")

    return DashboardControls(
        request=request,
        frequency_hz=frequency_hz,
        selected_drivers=selected_drivers,
    )


def _default_drivers(drivers: list[str]) -> list[str]:
    preferred = [driver for driver in ("VER", "LEC", "HAM", "NOR") if driver in drivers]
    if len(preferred) >= 2:
        return preferred[:2]
    return drivers[:2]
