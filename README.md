# F1 Telemetry Visualizer

Professional Formula 1 telemetry analysis and visualization platform built in Python.

Live app:

https://f1-telemetry-visualizer.streamlit.app/

This project combines FastF1 data ingestion, reusable telemetry processing, motorsport analytics, interactive Plotly visualizations, and a Streamlit dashboard.

The deployed dashboard uses a production-style data path:

```text
FastF1 local ingestion -> processed telemetry files -> Streamlit dashboard
```

Prepared sessions do not depend on a live FastF1 download when a visitor opens the
site. Live FastF1 remains available for sessions that have not been prepared, and a
clearly labelled demonstration dataset keeps the interface usable if the upstream
timing service is unavailable.

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

The included 2024 Italian Grand Prix qualifying comparison is prepared in advance,
so it opens without downloading FastF1 data at page-load time.

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

Prepare a session for reliable online use:

```powershell
.\.venv\Scripts\python.exe main.py prepare-session --year 2024 --grand-prix "Italian Grand Prix" --session Q --drivers VER LEC
```

Commit the generated folder under `data/processed/prebuilt/` and push it to GitHub.
The online dashboard will automatically use it before attempting a live download.

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

- `telemetry.ingestion`: FastF1 loading, cache setup, and processed telemetry storage
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
7 passed
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

FastF1 depends on external Formula 1 timing data sources. Prepared datasets isolate
the public dashboard from temporary upstream outages. The interface identifies its
active data source as prepared FastF1, live FastF1, or demonstration telemetry.

Generated local files are intentionally ignored by Git:

```text
.venv/
data/cache/
data/processed/*
logs/
reports/
__pycache__/
.pytest_cache/
```

`data/processed/prebuilt/` is intentionally committed because it contains the small,
analysis-ready datasets used by the deployed dashboard.
