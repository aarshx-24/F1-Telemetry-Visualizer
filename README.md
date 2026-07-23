# F1 Telemetry Visualizer

Professional Formula 1 telemetry analysis and visualization platform built in Python.

Live app:

https://f1-telemetry-visualizer.streamlit.app/

This project combines FastF1 data ingestion, reusable telemetry processing, motorsport analytics, interactive Plotly visualizations, and a Streamlit dashboard.

## What It Does

- Loads Formula 1 sessions using FastF1
- Caches race/session data for faster repeat analysis
- Extracts lap and telemetry data
- Compares fastest laps between drivers
- Aligns telemetry by distance for fair driver comparison
- Visualizes speed, throttle, brake, RPM, gear, and DRS traces
- Shows delta-time comparison
- Plots racing-line overlays and speed heatmaps
- Compares sector performance
- Estimates braking-zone behavior
- Computes consistency and pace metrics
- Estimates tyre degradation trends
- Performs lap clustering and anomaly detection
- Exports CSV data and HTML reports

## Use The Online App

Open:

https://f1-telemetry-visualizer.streamlit.app/

Recommended first test:

```text
Year: 2024
Grand Prix: Italian Grand Prix
Session: Q
Drivers: VER and LEC
Telemetry frequency: 10
```

The first load can take time because FastF1 may need to download session timing, car telemetry, and position data into the Streamlit Cloud cache.

If the app shows a FastF1 loading warning, click:

```text
Clear session cache
```

Then refresh or try another session.

## Run Locally

From the project folder:

```powershell
.\run_dashboard.bat
```

Then open:

http://localhost:8501

Manual Streamlit command:

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
|-- docs/
`-- tests/
```

## Architecture

The codebase is split into reusable layers:

- `telemetry.ingestion`: FastF1 session loading and cache setup
- `telemetry.processing`: telemetry cleaning, lap extraction, and distance alignment
- `telemetry.comparison`: driver-vs-driver comparison workflows
- `telemetry.analytics`: braking, consistency, tyre, corner, clustering, and anomaly analysis
- `telemetry.visualization`: reusable Plotly figure builders
- `dashboard`: Streamlit user interface
- `main.py`: command-line workflows

## Setup For Development

Create a virtual environment and install dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

If `py` is not available, use your installed Python executable directly.

## Verification

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected result:

```text
6 passed
```

## Deployment

This app is deployed on Streamlit Community Cloud.

Deployment settings:

```text
Repository: GitHub project repository
Branch: main
Main file path: dashboard/app.py
Python version: 3.12
Dependencies: requirements.txt
```

To update the deployed site:

1. Edit code locally.
2. Commit changes in VS Code or Git.
3. Push to GitHub.
4. Streamlit Cloud redeploys automatically.
5. If needed, click Reboot app in Streamlit Cloud.

## Notes

FastF1 depends on external Formula 1 timing data sources. If those services are slow or temporarily blocked, the app may show a loading warning. The dashboard includes fallback driver options and cache controls so the UI remains usable while data loading is retried.

Generated local files are intentionally ignored by Git:

```text
.venv/
data/cache/
data/processed/
logs/
reports/
__pycache__/
.pytest_cache/
```