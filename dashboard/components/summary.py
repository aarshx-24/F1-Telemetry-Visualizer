from __future__ import annotations

import streamlit as st

from telemetry.domain import LapTelemetry


def render_lap_metrics(laps: list[LapTelemetry]) -> None:
    if not laps:
        return

    columns = st.columns(min(len(laps), 4))
    for column, lap in zip(columns, laps, strict=False):
        with column:
            st.metric(
                label=lap.driver,
                value=f"{lap.lap_time_seconds:.3f}s",
                delta=f"Lap {lap.lap_number} | {lap.compound}",
            )
