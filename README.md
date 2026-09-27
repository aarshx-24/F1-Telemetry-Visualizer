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
site. Unprepared sessions use a bounded FastF1 download worker. If that service is
unavailable, the page shows a neutral availability message, not a traceback.
Synthetic data is available only through the explicit Demonstration mode.

## What It Does

- Loads Formula 1 sessions using FastF1
- Caches race/session data for faster repeat analysis
- Extracts lap and telemetry data
- Compares selected laps for two to four drivers, with a selectable reference
- Aligns telemetry by distance for fair driver comparison
- Visualizes speed, throttle, brake, RPM, gear, and DRS traces
- Shows delta-time comparison
- Plots racing-line overlays and speed heatmaps
- Compares sector performance
- Estimates braking-zone behavior
- Computes consistency and pace metrics
- Filters pit, deleted, inaccurate, non-green and unusually slow laps with an audit
- Estimates stint pace trends with conditional 95% intervals and optional fuel scenarios
- Selects K-means groups using silhouette scores and reports seed stability
- Offers timing or distance-weighted driving features where telemetry is available
- Reports continuous Isolation Forest scores and descriptive feature deviations
- Exports CSV data and HTML reports

## Use The Online App

Open:

https://f1-telemetry-visualizer.streamlit.app/

Recommended first test:

```text
Data mode: Real sessions
Session source: Saved sessions
Available session: 2024 Italian Grand Prix Q
Drivers: VER and LEC
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
- `telemetry.application`: session orchestration and data provenance, with an injectable download client
- `telemetry.processing`: telemetry cleaning, lap extraction, and distance alignment
- `telemetry.comparison`: driver-vs-driver comparison workflows
- `telemetry.analytics`: braking, consistency, tyre, corner, clustering, and anomaly analysis
- `telemetry.visualization`: reusable Plotly figure builders
- `dashboard/app.py`: session and lap selection; `dashboard/views.py`: analysis presentation
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

Tests cover numerical analysis, legacy archives, atomic archive generations,
offline recovery, download deadlines, ML edge cases and Streamlit interactions.
Network access is not required by the test suite. See `docs/reliability_and_analytics.md`
for model assumptions and deployment checks.

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

1. Install the updated requirements and run tests locally.
2. Commit all changed code and newly added modules, not only `dashboard/app.py`.
3. Push to GitHub.
4. Streamlit Cloud redeploys automatically.
5. If needed, click Reboot app in Streamlit Cloud.

## Notes

Lap selectors show saved telemetry only by default. The separate online-lap option
exposes timing-only laps that require another download; their availability is not
guaranteed. Existing prepared archives contain fastest-lap telemetry per driver,
not every lap. A complete lap timing table does not imply complete telemetry storage.

The prepared catalog also includes **2023 Abu Dhabi Grand Prix qualifying** with
fastest-lap telemetry for 20 drivers. Commit the entire corresponding folder under
`data/processed/prebuilt/` to make it available on the deployed website.
Download status now distinguishes a busy worker, a deadline, a process-start failure
and an unsuccessful worker. It also shows the remaining retry cooldown. These
diagnostics do not claim to fix an unknown hosting/network failure; Cloud logs are
still needed to diagnose unavailable unprepared sessions.

FastF1 depends on external Formula 1 timing data sources. Prepared datasets isolate
the public dashboard from temporary upstream outages. The interface identifies its
active source and snapshot date. CSV exports and HTML charts preserve provenance.
This is FastF1 historical session loading, not a LiveF1 live-race streaming integration.

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
