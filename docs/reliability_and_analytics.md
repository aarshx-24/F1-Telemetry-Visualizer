# Reliability and analytical improvements

## Architecture and request flow

```text
dashboard/app.py (selection) -> application/SessionService
                                 |-> downloaded real archive
                                 |-> committed prepared real archive
                                 `-> ingestion/LiveSessionClient
                                       `-> isolated FastF1 worker -> atomic archive
dashboard/views.py -> processing/quality -> analytics -> visualization
```

The application service accepts a SessionClient protocol so download behavior can
be replaced in tests. FastF1 stays behind its adapter. Analysis modules do not
import Streamlit. Existing CLI workflows and version-1 prepared archives remain
supported; new archive writes use version 2 and immutable CSV generations.

## Download behavior

- Saved real sessions open automatically without contacting FastF1.
- Fetch another session requests real historical FastF1 telemetry automatically.
- A child process has a 180-second whole-download deadline; schedule refresh has 30 seconds.
- The loader makes at most two attempts. Rate-limit errors are not retried.
- A shared filesystem lock prevents concurrent download workers in one deployment.
- Failed requests have a 120-second cooldown. Refresh is not a rate-limit bypass.
- Successful downloads go to ignored `data/processed/downloaded/`.
- Manifest publication is atomic. Old CSV generations are retained so active
  readers remain valid. Long-running deployments need offline archival/retention
  maintenance; do not delete generations while visitors may be reading them.
- The app displays source, session and snapshot date. A failed refresh retains the
  existing real archive. Unavailable sessions never silently become synthetic.
- Server logs contain diagnostics. User-facing download failures use neutral
  status messages. Dependency/build errors still require deployment repair.

External services, hosting quotas and network policy cannot be guaranteed. A
successful local download does not prove that Streamlit Cloud can reach the same
endpoint. Committed prepared datasets are the reliable offline route for specific
sessions, not proof of live connectivity. Runtime downloads may disappear when
the hosting instance is replaced. For durable multi-instance deployment, replace
the filesystem adapter with object storage and a shared job queue/lock.

## Analytics

- The lap audit records exclusions and missing metadata. Pace trimming is relative
  to a driver's best eligible lap within each compound/stint, not another driver.
  Missing deleted/accuracy flags in older archives cannot be recovered by guessing.
- Deltas compare interpolated time on shared distance coverage. Discrete channels
  use previous-sample hold. Distance interpolation adds no measurement precision.
- DRS active codes are 10, 12 and 14. Missing values remain unknown.
- One-lap consistency has undefined spread/score, not a perfect score.
- Stint trend fits lap time against lap number, requiring four unique clean laps.
  A fuel scenario adds `assumed_gain * (lap_number - first_lap)` before fitting.
  Confidence intervals are conditional OLS intervals, not physical tyre-wear
  uncertainty. Qualifying, traffic, weather and correlated residuals limit validity.
- Position coverage is reported. Track overlays are recorded coordinate paths,
  not optimal lines, accurate GPS, or a physical model of grip utilisation.
- K-means standardises features. Automatic selection compares k=2..6 using
  silhouette; adjusted Rand index compares two random seeds on the same cohort.
  These are exploratory diagnostics, not evidence of generalisation.
- Driving features are distance-weighted mean speed/throttle, minimum speed,
  braking share and full-throttle share. Only laps with saved telemetry qualify;
  one fastest lap per selected driver is usually too little for clustering.
- Timing features include lap time, sector times and tyre life. Lap/sector
  redundancy and stint context can dominate clusters; groups are not driver skills.
- Isolation Forest reports a continuous score (higher is more unusual), a separate
  flag and a median/MAD feature deviation. The deviation is descriptive, not a
  causal explanation of the model. Disable slow-lap trimming to investigate slow
  anomalies while retaining pit/flag controls. An unusual lap is not necessarily bad.

## Held-out evaluation

Export lap CSVs from two distinct, comparable sessions, preferably the same circuit
and session type. Reference-only preprocessing prevents evaluation-set fitting.

```powershell
.\.venv\Scripts\python.exe main.py evaluate-ml --reference-csv reference.csv --evaluation-csv evaluation.csv
```

Output: `reports/held_out_scores.csv` and `reports/held_out_metrics.csv`.
Session/DataSource provenance is required; synthetic and overlapping sessions are
rejected. Without independently reviewed labels, metrics are score summaries only.
An optional `KnownAnomaly` column containing 0/1 enables precision, recall and
ROC-AUC when both classes are present. Do not derive ground truth from model output.
Multiple unseen sessions and reviewed labels are still needed for scientific validation.

## Deploy this revision

1. Run `python -m pip install -r requirements.txt -r requirements-dev.txt` in the environment.
2. Run `python -m pytest`. Include the new application, analytics, worker, view and test modules in the commit.
3. Push the deployment branch. Streamlit entry point remains `dashboard/app.py`.
4. Verify requirements rebuild successfully (including filelock and updated Streamlit).
5. Open Saved sessions and select 2024 Italian Grand Prix Q. Verify two driver traces,
   DRS, source caption and a downloadable CSV without a download request.
6. Try Fetch another session, 2024 Bahrain Grand Prix Q. If unavailable, inspect
   Manage app logs for HTTP/rate-limit/timeout/resource details, not repeated reboots.
7. Prepare additional real sessions locally using `main.py prepare-session` with
   canonical Grand Prix names and commit the resulting prebuilt dataset folders.

Full vehicle dynamics, optimal racing-line calculation, state-space tyre modelling,
strategy predictions and validated driver-skill scores are not implemented by this
revision. They require additional inputs and validation; the dashboard does not
claim these capabilities.
