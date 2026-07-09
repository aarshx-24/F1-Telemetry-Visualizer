# PHASE 1 - Understanding Formula 1 Telemetry and Setting Up the Project Foundation

## 1. Goal of the Step

Build the professional foundation for the F1 Telemetry Visualizer:

- a repeatable Python project layout
- isolated configuration
- a first FastF1 session ingestion boundary
- a smoke-test command-line entry point
- tests for the configuration layer

The purpose is not to draw a graph yet. The purpose is to make sure every future
feature has a clean place to live.

## 2. Concepts Being Learned

Telemetry is time-series data collected from the car. In FastF1, the core car
channels include speed, RPM, gear, throttle, brake, and DRS. Position data adds
coordinates that later allow racing-line plots and speed heatmaps.

Professional telemetry work starts by separating concerns:

- ingestion gets data from a provider
- processing cleans and aligns signals
- comparison turns aligned laps into driver-to-driver deltas
- analytics extracts racing insight
- visualization communicates patterns
- dashboard code lets users interact with the analysis

## 3. System Architecture

The current architecture uses a domain-first boundary:

```text
main.py
  -> config/settings.py
  -> telemetry/domain/models.py
  -> telemetry/ingestion/fastf1_session_loader.py
```

`main.py` does not know the details of FastF1 beyond calling a loader. That is
intentional. Later, the dashboard and notebooks can call the same ingestion layer
without duplicating provider logic.

## 4. Folder/File Structure

Phase 1 introduces:

```text
config/settings.py
telemetry/domain/models.py
telemetry/ingestion/base.py
telemetry/ingestion/fastf1_session_loader.py
tests/test_settings.py
main.py
requirements.txt
```

The empty package folders are also created now because they define the future
architecture before code starts spreading into ad hoc scripts.

## 5. Clean Code Implementation

The most important Phase 1 implementation is `FastF1SessionLoader`. It owns:

- importing FastF1
- enabling the cache
- loading a session
- returning a small `SessionSummary`

This keeps external API details out of the rest of the application.

## 6. Code Explanation

`ProjectSettings` centralizes filesystem paths. A racing analytics project can
generate many data artifacts, so paths should not be hardcoded throughout the app.

`SessionRequest` is a small immutable object representing the user intent:
season, Grand Prix, and session type.

`SessionSummary` is a small domain return object. It lets us smoke-test the loader
without exposing every FastF1 detail to the CLI.

## 7. Telemetry/Data Science Explanation

The first distinction to learn is lap timing versus telemetry.

Lap timing data says what happened at the lap level: lap time, sector times, tyre
compound, lap number, pit status, and track status.

Telemetry says how the lap happened: speed trace, throttle application, braking
state, RPM, gear, DRS, and position. In motorsport analysis, lap timing identifies
where to investigate; telemetry explains why the time was gained or lost.

## 8. Visualization Explanation

We delay charts until Phase 4. That is a professional choice. Charts are only as
good as the data pipeline underneath them. A speed trace looks simple, but it must
be based on correctly selected laps, consistent distance axes, and reliable cache
behavior.

## 9. Debugging Tips

- If `python` is not recognized, install Python 3.11+ or add it to PATH.
- If FastF1 is missing, run `python -m pip install -r requirements.txt`.
- If session loading is slow, keep the FastF1 cache enabled.
- If a Grand Prix name fails, try a more common event name such as `Monza`,
  `Bahrain`, `Silverstone`, or `Spanish Grand Prix`.

## 10. Common Mistakes

- Starting with one large notebook and no reusable ingestion layer.
- Calling FastF1 directly from plotting functions.
- Disabling cache and repeatedly downloading the same timing data.
- Comparing telemetry by sample index instead of by distance or time alignment.
- Mixing raw, processed, and report data in one folder.

## 11. Refactoring Suggestions

As the platform grows, promote stable contracts:

- `SessionLoader` for provider-level ingestion
- `TelemetryRepository` for stored processed datasets
- `LapSelector` for consistent fastest-lap and stint selection
- `TelemetryFrame` or schema helpers for required channel validation

## 12. Mini Challenges

1. Run the smoke test for a qualifying session.
2. Change the session to a race session and compare lap counts.
3. Read `SessionRequest` and explain why it is immutable.
4. Find where the cache path is configured.
5. Predict which module should own speed trace plotting in Phase 4.
