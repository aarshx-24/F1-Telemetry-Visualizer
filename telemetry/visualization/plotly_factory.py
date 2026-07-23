from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from telemetry.domain import LapTelemetry


DEFAULT_TEMPLATE = "plotly_dark"
DRIVER_COLORS = (
    "#5b8cff",
    "#ff4b3e",
    "#22c55e",
    "#f5c542",
)
DRIVER_DASHES = ("solid", "dash", "dot", "dashdot")


class TelemetryPlotFactory:
    """Create interactive Plotly figures for telemetry analysis."""

    def telemetry_overlay(
        self,
        laps: list[LapTelemetry],
        channel: str,
        *,
        title: str | None = None,
    ) -> go.Figure:
        fig = go.Figure()
        for index, lap in enumerate(laps):
            if channel not in lap.telemetry or "Distance" not in lap.telemetry:
                continue
            fig.add_trace(
                go.Scatter(
                    x=lap.telemetry["Distance"],
                    y=lap.telemetry[channel],
                    mode="lines",
                    name=lap.label,
                    line={
                        "color": DRIVER_COLORS[index % len(DRIVER_COLORS)],
                        "dash": DRIVER_DASHES[index % len(DRIVER_DASHES)],
                        "width": 2.5,
                    },
                    opacity=0.95,
                    hovertemplate="Distance %{x:.0f} m<br>%{y:.2f}<extra></extra>",
                )
            )

        return self._finish_trace_layout(
            fig,
            title or f"{channel} trace",
            y_axis=channel,
        )

    def delta_trace(self, aligned: pd.DataFrame) -> go.Figure:
        fig = go.Figure()
        if "DeltaSeconds" in aligned and "Distance" in aligned:
            fig.add_trace(
                go.Scatter(
                    x=aligned["Distance"],
                    y=aligned["DeltaSeconds"],
                    mode="lines",
                    name="Delta",
                    line={"color": "#ff4b4b", "width": 2},
                    hovertemplate="Distance %{x:.0f} m<br>Delta %{y:.3f}s<extra></extra>",
                )
            )
            fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#7dd3fc")

        return self._finish_trace_layout(fig, "Delta time", y_axis="Seconds")

    def track_speed_map(self, lap: LapTelemetry) -> go.Figure:
        telemetry = lap.telemetry
        if not {"X", "Y", "Speed"}.issubset(telemetry.columns):
            return self.empty("Track position data is not available for this lap.")

        fig = px.scatter(
            telemetry,
            x="X",
            y="Y",
            color="Speed",
            color_continuous_scale="Turbo",
            template=DEFAULT_TEMPLATE,
            title=f"Speed heatmap - {lap.label}",
        )
        fig.update_traces(marker={"size": 5})
        fig.update_yaxes(scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False)
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_layout(
            height=620,
            margin={"l": 20, "r": 20, "t": 56, "b": 20},
            coloraxis_colorbar={"title": "km/h"},
        )
        return fig

    def track_overlay(self, laps: list[LapTelemetry]) -> go.Figure:
        fig = go.Figure()
        for index, lap in enumerate(laps):
            telemetry = lap.telemetry
            if not {"X", "Y"}.issubset(telemetry.columns):
                continue
            fig.add_trace(
                go.Scatter(
                    x=telemetry["X"],
                    y=telemetry["Y"],
                    mode="lines",
                    name=lap.label,
                    line={
                        "color": DRIVER_COLORS[index % len(DRIVER_COLORS)],
                        "dash": DRIVER_DASHES[index % len(DRIVER_DASHES)],
                        "width": 3,
                    },
                    hovertemplate="X %{x:.0f}<br>Y %{y:.0f}<extra></extra>",
                )
            )

        fig.update_yaxes(scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False)
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_layout(
            template=DEFAULT_TEMPLATE,
            title="Racing line overlay",
            height=620,
            margin={"l": 20, "r": 20, "t": 56, "b": 20},
            legend={"orientation": "h", "y": 1.02, "x": 0},
        )
        return fig

    def sector_bars(self, sector_table: pd.DataFrame) -> go.Figure:
        if sector_table.empty:
            return self.empty("Sector data is not available.")

        melted = sector_table.melt(
            id_vars=["Driver"],
            value_vars=[column for column in ("Sector1", "Sector2", "Sector3") if column in sector_table],
            var_name="Sector",
            value_name="Seconds",
        )
        fig = px.bar(
            melted,
            x="Sector",
            y="Seconds",
            color="Driver",
            barmode="group",
            template=DEFAULT_TEMPLATE,
            title="Sector comparison",
        )
        fig.update_layout(height=430, margin={"l": 20, "r": 20, "t": 56, "b": 20})
        return fig

    def lap_time_scatter(self, lap_table: pd.DataFrame) -> go.Figure:
        if lap_table.empty or "LapTimeSeconds" not in lap_table:
            return self.empty("Lap timing data is not available.")

        fig = px.scatter(
            lap_table.dropna(subset=["LapTimeSeconds"]),
            x="LapNumber",
            y="LapTimeSeconds",
            color="Driver",
            symbol="Compound" if "Compound" in lap_table else None,
            template=DEFAULT_TEMPLATE,
            title="Lap time evolution",
        )
        fig.update_layout(height=520, margin={"l": 20, "r": 20, "t": 56, "b": 20})
        return fig

    def tire_degradation(self, tire_table: pd.DataFrame) -> go.Figure:
        if tire_table.empty:
            return self.empty("Not enough stint data for tyre degradation.")

        fig = px.bar(
            tire_table,
            x="Driver",
            y="DegradationPerLap",
            color="Compound",
            facet_col="Stint",
            template=DEFAULT_TEMPLATE,
            title="Estimated tyre degradation per lap",
        )
        fig.update_layout(height=460, margin={"l": 20, "r": 20, "t": 56, "b": 20})
        return fig

    def cluster_scatter(self, clustered_laps: pd.DataFrame) -> go.Figure:
        if clustered_laps.empty:
            return self.empty("Not enough lap data for clustering.")

        fig = px.scatter(
            clustered_laps,
            x="LapNumber",
            y="LapTimeSeconds",
            color="Cluster",
            symbol="Driver",
            hover_data=[column for column in ("Compound", "TyreLife") if column in clustered_laps],
            template=DEFAULT_TEMPLATE,
            title="Lap clustering",
        )
        fig.update_layout(height=520, margin={"l": 20, "r": 20, "t": 56, "b": 20})
        return fig

    def empty(self, message: str) -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 18},
        )
        fig.update_layout(
            template=DEFAULT_TEMPLATE,
            height=420,
            xaxis={"visible": False},
            yaxis={"visible": False},
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
        )
        return fig

    @staticmethod
    def _finish_trace_layout(fig: go.Figure, title: str, *, y_axis: str) -> go.Figure:
        fig.update_layout(
            template=DEFAULT_TEMPLATE,
            title=title,
            height=430,
            hovermode="x unified",
            margin={"l": 20, "r": 20, "t": 56, "b": 20},
            legend={"orientation": "h", "y": 1.02, "x": 0},
        )
        fig.update_xaxes(title="Distance [m]")
        fig.update_yaxes(title=y_axis)
        return fig
