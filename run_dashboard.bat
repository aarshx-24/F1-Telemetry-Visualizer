@echo off
cd /d "%~dp0"
echo Starting F1 Telemetry Visualizer...
echo Keep this terminal window open while using the dashboard.
".venv\Scripts\python.exe" -m streamlit run "dashboard\app.py" --server.port 8501 --server.address localhost --server.headless true
echo.
echo Dashboard stopped. Press any key to close this window.
pause >nul
