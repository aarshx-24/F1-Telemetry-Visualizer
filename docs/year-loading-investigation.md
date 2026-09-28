# Year-dependent FastF1 loading investigation

## Status

The reported Cloud failure is **not reproduced locally**. Its underlying exception
is still required from the deployed application's server logs. The changes below
repair confirmed diagnostic/control defects; they do not establish that Cloud
downloads are repaired. No interface rebuild, synthetic fallback, or prepared-data
substitution was introduced.

## Real-data evidence (2026-09-28)

Environment: project `.venv`, Python 3.12.14, FastF1 3.8.3, Streamlit 1.58.0.
The working 2022 comparison was assumed to be Italian qualifying; confirmation of
the user's exact working event was requested.

| Probe | Result |
| --- | --- |
| Original app: 2022 Italian Q | 260 lap records, 20 drivers, 12 charts |
| Same app: switch to 2023 Italian Q | 327 lap records, 20 drivers, 12 charts |
| Switch back to 2022 | 20 drivers, 12 charts, no error |
| Switch to 2024 Italian Q | 276 lap records, 20 drivers, 12 charts |
| Fresh Streamlit run starting directly at 2023 Italian Q | 20 drivers, 12 charts |
| Standalone 2023 Italian Q, separate empty FastF1 cache | 327 lap records, 20 drivers, 603 VER telemetry samples |
| Standalone 2023 Bahrain Q, separate empty FastF1 cache | 254 lap records, 20 drivers, 654 VER telemetry samples |
| Patched app: 2022 -> 2023 -> 2022 -> 2024 | 20 drivers and 12 charts at every step |

These are actual FastF1 datasets, not mocked network results. Lap counts include
all available records, not only valid competitive laps. The empty-cache probes
used new directories, without deleting or repairing the existing app cache.

## Findings mapped to the request

1. The original transition was exercised through Streamlit AppTest before edits.
2. No FastF1 exception occurred in these local real-data runs. Therefore there is
   no genuine local failure traceback to present as the Cloud cause. The original
   loader hid FastF1 warnings and DEBUG tracebacks by forcing ERROR logging.
   FastF1's `soft_exceptions` wrapper logs the real internal exception at DEBUG,
   then can leave an incomplete session. This explains missing diagnostic detail,
   not why the upstream load failed on Cloud.
3. Fresh 2023 loading and a transition into 2023 both succeeded.
4. No application session-state assignments or lap selectors existed in the
   restored code. Widget states were implicit. Explicit year/event/session keys
   now keep event, session-type and driver selections scoped to their dataset.
5. The resource-cache argument was already the immutable SessionRequest containing
   year, Grand Prix and session type. Schedule caching already included the year.
   FastF1 resolved Italian GP to round 16 in 2022, round 14 in 2023, round 16 in 2024.
   There is no reused app round number. The 2023 API path was
   `/static/2023/2023-09-03_Italian_Grand_Prix/2023-09-02_Qualifying/`.
6. No prepared-data or demo fallback is used by the restored app. It does have a
   static event-name fallback if schedule loading fails. Canonical names now must
   resolve exactly, preventing FastF1 fuzzy search from silently choosing another
   event. Session-type validity remains checked by FastF1 against the selected
   event. The configured year range includes all tested years. Empty telemetry
   dictionaries are now rejected before a session enters the Streamlit cache.
7. The standalone script imports FastF1 directly, without the application loader.
8. Bahrain 2023 and Italian 2024 also loaded as noted above.
9. The confirmed disappearing-control cause was the early `return` after a failed
   load, before `render_driver_controls`. There is no `st.stop()` on this path.
10. The disabled driver selector is now rendered on failure with an explanation.
    Full exception chains and resolved request metadata are logged on the server.
    Successful resources are limited to two entries rather than unbounded sessions.
    This bounds retention; it is not evidence of a Cloud out-of-memory diagnosis.

## Reproduce

Run from the project root, one command at a time:

```powershell
.\.venv\Scripts\python.exe scripts/diagnose_sessions.py --mode transition
.\.venv\Scripts\python.exe scripts/diagnose_sessions.py --mode fresh --year 2023
.\.venv\Scripts\python.exe scripts/diagnose_sessions.py --mode standalone --year 2023 --fresh-cache
.\.venv\Scripts\python.exe scripts/diagnose_sessions.py --mode standalone --year 2023 --event "Bahrain Grand Prix" --fresh-cache
```

Logs and JSON summaries are under `logs/year-diagnostics/` (ignored by Git).
`--fresh-cache` downloads data into a separate diagnostic cache and consumes disk
space/network traffic. These opt-in probes are not run by the offline test suite.

Baseline evidence files:
- `transition_2023_1790569481159107000.json`
- `fresh_2023_1790569623765445800.json`
- `standalone_2023_1790569572246270600.json` (Italian)
- `standalone_2023_1790569701882802700.json` (Bahrain)
- `transition_2023_1790569799120060600.json` (after targeted changes)

## Remaining Cloud evidence

Deploy the targeted logging change, reproduce the failing 2023 session once, then
capture the first FastF1 warning, its `Traceback for failure in ...` DEBUG record,
and the application's `Session load failed [reference]` chain. Record the resolved
event path and installed FastF1 version. Remove credentials before sharing logs.
Compare the same event/year/session on Cloud, not merely a different 2022 event.
Do not infer rate limits, missing data, dependency defects or memory exhaustion
until the traceback supports that conclusion. No changes have been pushed here.
