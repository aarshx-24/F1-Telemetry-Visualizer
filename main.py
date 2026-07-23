from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.io as pio

from config.settings import build_settings
from telemetry.comparison import DriverComparisonService
from telemetry.domain import ExportedReport, SessionRequest
from telemetry.ingestion import (
    FastF1DataLoadError,
    FastF1NotInstalledError,
    FastF1SessionLoader,
    ProcessedTelemetryStore,
)
from telemetry.processing import TelemetryExtractor
from telemetry.visualization import TelemetryPlotFactory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F1 Telemetry Visualizer")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["summary", "compare", "export-laps", "prepare-session", "dashboard"],
        default="summary",
    )
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--grand-prix", default="Monza")
    parser.add_argument("--session", default="Q")
    parser.add_argument("--drivers", nargs="+", default=["VER", "LEC"])
    parser.add_argument("--frequency", type=int, default=10)
    parser.add_argument("--port", type=int, default=8501)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = build_settings()
    settings.ensure_directories()

    request = SessionRequest(
        year=args.year,
        grand_prix=args.grand_prix,
        session_type=args.session,
    )
    loader = FastF1SessionLoader(settings=settings)

    try:
        if args.command == "dashboard":
            return launch_dashboard(settings.project_root, args.port)
        if args.command == "compare":
            report = build_comparison_report(
                loader,
                request,
                drivers=args.drivers,
                frequency=args.frequency,
            )
            print(f"Report written: {report.path}")
            return 0
        if args.command == "export-laps":
            path = export_lap_table(loader, request, settings.processed_data_dir)
            print(f"Lap table written: {path}")
            return 0
        if args.command == "prepare-session":
            path = prepare_session_dataset(
                loader,
                request,
                settings.processed_data_dir / "prebuilt",
                drivers=args.drivers,
                frequency=args.frequency,
            )
            print(f"Prepared telemetry written: {path}")
            return 0

        summary = loader.load_session_summary(request)
        print(summary.to_console_text())
        return 0
    except (FastF1NotInstalledError, FastF1DataLoadError) as exc:
        print(exc)
        if isinstance(exc, FastF1NotInstalledError):
            print("Install dependencies with: python -m pip install -r requirements.txt")
        return 1


def launch_dashboard(project_root: Path, port: int) -> int:
    app_path = project_root / "dashboard" / "app.py"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.address",
        "localhost",
    ]
    return subprocess.call(command, cwd=project_root)


def build_comparison_report(
    loader: FastF1SessionLoader,
    request: SessionRequest,
    *,
    drivers: list[str],
    frequency: int,
) -> ExportedReport:
    session = loader.load_session(request, telemetry=True)
    comparison = DriverComparisonService().compare_fastest_laps(
        session,
        request,
        drivers,
        frequency=frequency,
    )
    plotter = TelemetryPlotFactory()
    figures = [
        plotter.telemetry_overlay(list(comparison.laps), "Speed", title="Speed comparison"),
        plotter.telemetry_overlay(list(comparison.laps), "Throttle", title="Throttle comparison"),
        plotter.telemetry_overlay(list(comparison.laps), "Brake", title="Brake comparison"),
        plotter.delta_trace(comparison.aligned),
        plotter.track_overlay(list(comparison.laps)),
        plotter.sector_bars(comparison.sector_table),
    ]

    report_path = _report_path(loader, request, drivers)
    sections = [
        pio.to_html(fig, full_html=False, include_plotlyjs="cdn" if index == 0 else False)
        for index, fig in enumerate(figures)
    ]
    html = _wrap_report_html(request, drivers, comparison.insights, sections)
    report_path.write_text(html, encoding="utf-8")
    return ExportedReport(report_path, "Driver comparison report")


def export_lap_table(
    loader: FastF1SessionLoader,
    request: SessionRequest,
    output_dir: Path,
) -> Path:
    session = loader.load_session(request, telemetry=False)
    table = TelemetryExtractor().lap_table(session)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"laps_{request.year}_{_slug(request.grand_prix)}_{request.session_type}.csv"
    table.to_csv(path, index=False)
    return path


def prepare_session_dataset(
    loader: FastF1SessionLoader,
    request: SessionRequest,
    output_dir: Path,
    *,
    drivers: list[str],
    frequency: int,
) -> Path:
    """Download once locally and store only analysis-ready dashboard data."""

    session = loader.load_session(request, telemetry=True)
    extractor = TelemetryExtractor()
    comparison = DriverComparisonService(extractor=extractor).compare_fastest_laps(
        session,
        request,
        drivers,
        frequency=frequency,
    )
    lap_table = extractor.lap_table(session)
    circuit_info = session.get_circuit_info()
    corners = pd.DataFrame(getattr(circuit_info, "corners", pd.DataFrame())).copy()
    store = ProcessedTelemetryStore(output_dir)
    return store.save(
        comparison,
        lap_table,
        corners,
        frequency_hz=frequency,
    )


def _report_path(
    loader: FastF1SessionLoader,
    request: SessionRequest,
    drivers: list[str],
) -> Path:
    reports_dir = loader.settings.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    driver_slug = "_".join(drivers)
    return reports_dir / (
        f"comparison_{request.year}_{_slug(request.grand_prix)}_"
        f"{request.session_type}_{driver_slug}.html"
    )


def _wrap_report_html(
    request: SessionRequest,
    drivers: list[str],
    insights: tuple[str, ...],
    sections: list[str],
) -> str:
    insight_items = "\n".join(f"<li>{insight}</li>" for insight in insights)
    section_html = "\n".join(sections)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>F1 Telemetry Report - {request.label}</title>
  <style>
    body {{ margin: 0; padding: 24px; background: #0f172a; color: #f8fafc; font-family: Arial, sans-serif; }}
    h1, h2 {{ letter-spacing: 0; }}
    .meta {{ color: #cbd5e1; margin-bottom: 24px; }}
    .panel {{ background: #111827; border: 1px solid #243244; border-radius: 8px; padding: 16px; margin: 18px 0; }}
  </style>
</head>
<body>
  <h1>F1 Telemetry Report</h1>
  <div class="meta">{request.label} | Drivers: {", ".join(drivers)}</div>
  <div class="panel"><h2>Insights</h2><ul>{insight_items}</ul></div>
  {section_html}
</body>
</html>
"""


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")


if __name__ == "__main__":
    raise SystemExit(main())
