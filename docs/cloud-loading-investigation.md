# Streamlit Cloud investigation - 28 September 2026

## Status

The Cloud failure is reproduced, not yet repaired or explained at the upstream-error level.
Calendar validation and build diagnostics are corrected locally. No new deployment was
performed in this investigation. Do not describe local success as Cloud verification.

## Deployment attribution

Evidence file: `logs-aarshx-24-f1-telemetry-visualizer-main-dashboard-app.py-2026-09-28T04_45_16.147Z.txt`.
Line numbers below refer to that downloaded file. Its deployment records do not contain Git SHAs.
Commit times alone establish a plausible sequence, not proof of what each process executed.

| Log interval (UTC) | Evidence and attribution |
| --- | --- |
| 27 September 20:04:23 to 20:23:55 | Worker/two-attempt loader, lines 130-448. Source matches the loader shared by `3aecdea` and `6d34b8c`; the 19:59:23 commit time makes `3aecdea` consistent with the initial deployment. Cannot distinguish these revisions by the loader alone. |
| 20:23:55 update to 20:33:48 | Consistent with `6d34b8c`, committed at 20:23:51. No SHA recorded. |
| 20:33:48 update | Consistent with restoration `94691cd` at 20:33:40. Lines 493-510 show shutdown and restart; a two-attempt loader failure occurs during shutdown and must not be attributed to the new process. |
| 28 September 04:36:53 update | Consistent with `84361df`, committed at 04:36:47. Lines 1133-1272 show new app logging combined with old loader behavior. |
| 04:44:21 pull / 04:44:23 updated | Lines 1373 onward. No subsequent session failure is recorded in the supplied export. Exact deployed SHA and successful 2023/2024 loading are not established. |

The late tracebacks use loader lines 47 and 114, matching `94691cd`'s validation
call and `laps = session.laps`. The displayed source text instead belongs to
`84361df` (including `return COMMON_GRAND_PRIX_NAMES` inside what the traceback
calls `_validate_loaded_session`). The exception also contains the old generic
cache advice, which `84361df` removed. Meanwhile, the app emits the new
`Dashboard session failure` message. This is strong evidence of mixed executing
and on-disk code, consistent with a stale imported module during hot updates.
It does not identify the underlying FastF1 download/parsing exception.

New `APP_RUNTIME` records include checkout revision, package versions, app/loader
disk hashes and the loader's import-time hash. `STALE_LOADER` reports a mismatch.
A checkout SHA alone does not identify uncommitted or already-imported code.

## Exact loading path and missing evidence

Current application: `get_session(year, event, session_type)`, then
`session.load(laps=True, telemetry=True, weather=True, messages=False)`, then
validation of nonempty laps, car data and position data. Validation is not called
before loading. The old worker version used `weather=False` and two attempts.

FastF1 3.8.3 catches some internal loading exceptions in `soft_exceptions`, logs
a warning and a DEBUG traceback, then continues. The old application's ERROR
logging threshold hid these records. Accessing `session.laps` subsequently raised
`DataNotLoadedError`. The missing earlier exceptions cannot be recovered from this export.

The current loader enables DEBUG and timestamps FastF1 records before schedule/session
loading. Load start, resolved event/round/API path, cache directory, success counts,
duration, and full exception chains are logged. The current restored app has no
telemetry subprocess worker. The reproducibility runner captures both stdout and
stderr from every diagnostic child process into a separate log file.

## Calendar, state and caching

- Confirmed defect: failed/empty schedules returned a static all-years event list,
  including `70th Anniversary Grand Prix`. This offered invalid 2023/2024 choices.
- Fixed: unavailable calendars now raise an explicit error; no unverified names
  are offered. Grand Prix and Drivers stay visible but disabled, with retry guidance.
- Existing canonical-name validation prevents silently fuzzy-matching another event.
- Request keys include year, event and session; event and driver widget keys include
  year/session identity. The app does not store a round from the previous year.
- Source/environment fingerprint now also participates in both Streamlit cache keys,
  preventing old calendar fallback lists or session objects from crossing builds.
- Failed loads raise before the resource cache can retain them. Existing FastF1
  disk caches are preserved; cache deletion is not treated as a fix.

## Dependency comparison

Cloud explicitly used `uv pip install` with root `requirements.txt` and Python 3.12.14.
Its warning about `pyproject.toml` describes alternative dependency files, not a
demonstrated version conflict. Root requirements match project dependencies plus
the analytics/dashboard extras. A regression test now checks that equivalence.
`pyproject.toml`, its metadata, extras and pytest settings remain intact.

| Dependency | Existing successful local environment | Cloud log |
| --- | --- | --- |
| Python | 3.12.14 | 3.12.14 |
| FastF1 | 3.8.3 | 3.8.3 |
| pandas | 2.3.3 | 2.3.3 |
| Streamlit | 1.58.0 | 1.64.0 |
| NumPy | 2.4.6 | 2.5.3 |
| SciPy | 1.17.1 | 1.18.1 |
| scikit-learn | 1.8.0 | 1.9.1 |
| requests-cache | 1.3.2 | 1.3.3 |
| urllib3 | 2.7.0 | 2.8.0 |
| Plotly | 6.7.0 | 6.9.0 |
| matplotlib | 3.10.9 | 3.11.2 |
| PyArrow | 24.0.0 | 24.0.0 after Cloud's automatic replacement |

Earlier local tests reused `.venv`; they were not a clean requirements installation.
The original installation command/history is not established by the available evidence.

This investigation created `logs/cloud-repro/venv` with Python 3.12.14 and installed
using uv, root requirements, and constraints extracted from the supplied Cloud log.
The resolved required packages match that snapshot. Platform-specific packages differ
(Windows versus Linux); uv itself is an extra tooling package. Cloud's leftover
filelock is not required by the restored requirements. Dependency consistency passes.

Full chart verification in that environment is blocked by Windows Application Control:
SciPy's `_linalg_pythran` DLL cannot load. This is a local policy failure, not evidence
of the Linux Cloud cause. No security policy was disabled and no speculative downgrade
was applied. Raw FastF1 session loading does not require that interpolation step.

## Results with real data

All cold probes below used distinct new empty FastF1 caches and the Cloud-version environment.
Raw sample counts are the selected driver's full-session car samples, not one interpolated lap.

| Qualifying session | Lap records | Drivers | Raw VER car samples | Result |
| --- | ---: | ---: | ---: | --- |
| 2022 Italian | 260 | 20 | 17591 | Passed |
| 2023 Italian | 327 | 20 | 17405 | Passed |
| 2023 Bahrain | 254 | 20 | 19742 | Passed |
| 2024 Italian | 276 | 20 | 17406 | Passed |

Full stdout/stderr: `logs/cloud-repro/1790571953621481600/`.
Installation, package freeze and blocked interpolation evidence:
`logs/cloud-repro/1790571755468693800/`.

The cold 2022 run explicitly fetched data and used FastF1's official live-timing
mirror fallback. The 2023 Italian probe fetched without mirror messages. This
establishes different local upstream paths, not which path Cloud used.
The supplied Cloud log does not establish 2022 cache provenance. The restored
app has no prepared/synthetic fallback or special 2022 branch.

Existing local environment: full AppTest transition 2022 -> 2023 -> 2022 -> 2024
passed with 20 drivers and 12 charts at every step. A separate fresh 2023 AppTest
also passed. These dashboard runs used the existing FastF1 disk cache.
Evidence: `logs/year-diagnostics/transition_2023_1790571972067710600.json` and
`logs/year-diagnostics/fresh_2023_1790572179841777500.json`.
Offline regression suite: 19 passed.

Public Cloud browser checks during this investigation:
- 2022 Italian Q renders VER 80.306s and LEC 80.161s, driver controls and charts.
- Switching from 2022 to 2023 Italian Q fails; Drivers remains visible but disabled.
- An independent browser tab selecting 2023 without visiting 2022 also fails.
  The tab initially ran the app's default 2024; this is not a fresh server process.
- 2023 Bahrain Q and default 2024 Italian Q also fail.
- Failure text is still the old loader's generic cache advice, not a new reference ID.

## Management/log panel: separate investigation

The public browser exposes Fork, not owner Manage app access. Its captured browser
console has no warning/error records. The supplied server log contains a successful
health check during one update and no recorded OOM or WebSocket failure; this does
not rule out resource or connectivity problems at other times. Owner-panel access
while loading could not be tested. No evidence establishes a shared cause with FastF1.
The app does not implement or control Streamlit Cloud's management panel.

## Remaining Cloud verification

1. Commit/push the focused changes, including the new utility module; they are local only.
2. Restart the Cloud server process after deployment so imported modules match disk.
   This is build verification, not a claim that clearing caches fixes data loading.
3. Confirm the new `APP_RUNTIME` revision and matching source hashes in owner logs.
4. Test 2022 -> 2023 -> 2024 Italian Q and 2023 Bahrain Q. Capture logs from
   `Session load` through the first internal warning/DEBUG traceback and final outcome.
5. If failure persists, diagnose that original exception/HTTP evidence. Do not substitute
   demo data, blindly downgrade packages, or infer the cause from `DataNotLoadedError`.
6. Test owner log access both idle and loading, recording browser console/network failures
   separately and redacting credentials before sharing them.

GitHub remote verification was blocked locally by a Schannel credential error.
No commit, push, owner reboot or post-patch Cloud verification was performed.
