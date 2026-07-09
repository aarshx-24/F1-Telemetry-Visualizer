# F1 Telemetry Visualizer

Professional Formula 1 telemetry analysis platform built completely in Python.

This is now a runnable end-to-end project with:

- FastF1 session loading and cache management
- lap and telemetry extraction
- distance-based telemetry alignment
- driver fastest-lap comparison
- speed, throttle, brake, gear, RPM, DRS-ready traces
- delta timing
- racing-line overlays and speed heatmaps
- sector comparison
- braking-zone analysis
- tyre degradation estimation
- consistency metrics
- lap clustering and anomaly detection
- Streamlit dashboard
- HTML report export
- CSV data export

## Open the Dashboard

From this project folder:

```powershell
.\run_dashboard.bat
```

Then open:

[http://localhost:8501](http://localhost:8501)

You can also run it manually:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8501
```

## CLI Commands

Session summary:

```powershell
.\.venv\Scripts\python.exe main.py summary --year 2024 --grand-prix Monza --session Q
```

Generate an interactive HTML telemetry report:

```powershell
.\.venv\Scripts\python.exe main.py compare --year 2024 --grand-prix Monza --session Q --drivers VER LEC
```

Export lap timing data:

```powershell
.\.venv\Scripts\python.exe main.py export-laps --year 2024 --grand-prix Monza --session Q
```

Launch dashboard through the CLI:

```powershell
.\.venv\Scripts\python.exe main.py dashboard
```

## Project Structure

```text
project_root/
|-- main.py
|-- run_dashboard.bat
|-- requirements.txt
|-- config/
|-- data/
|   |-- raw/
|   |-- processed/
|   `-- cache/
|-- telemetry/
|   |-- domain/
|   |-- ingestion/
|   |-- processing/
|   |-- analytics/
|   |-- comparison/
|   `-- visualization/
|-- dashboard/
|   |-- app.py
|   |-- pages/
|   |-- components/
|   `-- layouts/
|-- models/
|-- utils/
|-- notebooks/
|-- reports/
|-- docs/
`-- tests/
```

## Architecture

The codebase separates responsibilities:

- `telemetry.ingestion` owns FastF1 loading and cache setup.
- `telemetry.processing` cleans telemetry, extracts laps, and aligns signals by distance.
- `telemetry.comparison` coordinates driver-vs-driver analysis.
- `telemetry.analytics` computes braking, consistency, degradation, corner, clustering, and anomaly insights.
- `telemetry.visualization` creates reusable Plotly figures.
- `dashboard` contains the Streamlit UI.
- `main.py` exposes CLI workflows.

## Setup

If `.venv` is missing, create it and install the full stack:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

If your machine does not expose `py`, use the full path to your Python executable.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected result:

```text
6 passed
```

## Generated Artifacts

Example outputs already generated:

- `reports/comparison_2024_monza_Q_VER_LEC.html`
- `data/processed/laps_2024_monza_Q.csv`

FastF1 cache is stored in:

```text
data/cache/
```
