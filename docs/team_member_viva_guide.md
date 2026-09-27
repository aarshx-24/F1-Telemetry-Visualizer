# F1 Telemetry Visualizer - Team Viva Guide

This guide matches the implemented project. It gives each member a focused explanation, likely supervisor questions, and short accurate answers. Every member should understand the overall flow because evaluators can ask cross-team questions.

## Project in One Minute

F1 Telemetry Visualizer is a Python and Streamlit web application that transforms Formula 1 session data into interactive driver-comparison and telemetry-analysis views. It uses FastF1 to access live session data, pandas and NumPy to prepare telemetry, Plotly to display charts, and scikit-learn for lap clustering and anomaly detection. For reliable online deployment, the app first uses prepared session data when available, then tries live FastF1 data, and only then shows clearly labelled demonstration data if required.

## Team Contribution Summary

| Member | Role | Main contribution |   |
|---|---|---|---:|
| Dhruv Singh | Project Architecture and Backend | Project structure, configuration, domain separation, command-line workflow, and module integration |   |
| Vedansh Singh Tomar | Data Ingestion | FastF1 loading, cache configuration, validation, and prepared-session storage |   |
| Avika Singh | Telemetry Processing | Data cleaning, time conversion, fastest-lap extraction, and distance-based interpolation |  |
| Arsh Arun | Analytics and ML | Sectors, delta, braking, corner analysis, consistency, tyre trend, clustering, and anomaly detection |   |
| Kanishka | Frontend and Visualization | Streamlit controls/tabs and interactive Plotly telemetry, track, sector, and analytics charts |   |
| Soumya Tandon | Testing, Documentation, and Deployment | pytest tests, CSV/HTML reports, README/presentation, GitHub workflow, and Streamlit Cloud deployment |   |

---

# 1. Dhruv Singh - Project Architecture and Backend

## Responsibility

Dhruv designed the professional project structure and coordinated the backend workflow. The project is divided into dedicated modules instead of one large script:

- `telemetry.ingestion` loads FastF1 or prepared data.
- `telemetry.processing` cleans and aligns telemetry.
- `telemetry.analytics` calculates insight metrics and ML outputs.
- `telemetry.comparison` coordinates driver-versus-driver analysis.
- `telemetry.visualization` creates reusable Plotly figures.
- `dashboard` contains the Streamlit interface.
- `main.py` provides command-line workflows.

##  Explanation

"Role was project architecture and backend integration. I structured the application into separate modules for ingestion, processing, analytics, comparison, visualization, dashboard, and utilities. This follows clean architecture principles because each module has one clear responsibility. For example, the dashboard does not directly download FastF1 data, and the chart code does not contain data-cleaning logic. This design makes the project easier to test, debug, reuse, and extend. I also worked on configuration, domain separation, and command-line workflows so the same core system can be used from the Streamlit dashboard or from Python commands."

## Key Technical Points

- Clean architecture separates responsibilities and avoids a monolithic `app.py`.
- Reusable services make future changes safer.
- Backend coordinates data flow but does not own chart presentation.
- `main.py` supports summary, comparison, CSV export, session preparation, and dashboard launch workflows.

## Likely Questions and Answers

| Question | Short answer |
|---|---|
| What is clean architecture? | It is a design approach that separates responsibilities so each module has a focused purpose and lower coupling with other modules. |
| Why did you not write everything in one Python file? | One large file becomes difficult to test, debug, maintain, and extend. Separate modules make changes safer. |
| What is the backend in this project? | The backend is the Python logic that loads data, processes telemetry, runs analytics, and provides results to the dashboard. |
| What is the role of `main.py`? | It is the command-line entry point for tasks such as session summary, driver comparison, CSV export, preparing data, and launching the dashboard. |
| How do modules communicate? | Higher-level services call lower-level reusable modules through clear function and class interfaces. For example, the dashboard requests processed data rather than directly manipulating raw FastF1 objects. |
| Why are ingestion and visualization separate? | Data loading can fail or change independently from charts. Separation makes error handling and reuse easier. |
| How does this structure help testing? | Processing and analytics functions can be tested using small sample DataFrames without opening the UI or downloading live data. |
| What is the advantage of reusable code? | The same processing and analytics logic can support the dashboard, CLI reports, tests, and future APIs. |
| How would you add another data source later? | Add a new ingestion adapter that returns the same structured data expected by the processing layer. The dashboard and analytics layers need minimal changes. |
| What happens when a module fails? | The system can handle failure at the responsible layer and provide a clear message or fallback instead of crashing the entire application. |
| Is this a microservices architecture? | No. It is a modular monolithic Python application. Modules are separated inside one project, not deployed as independent network services. |
| Why is modular architecture useful in a team project? | Different members can work on different modules with less conflict, while the interfaces keep their work compatible. |

---

# 2. Vedansh Singh Tomar - Data Ingestion

## Responsibility

Vedansh implemented the data-entry path of the project:

- FastF1 session loading.
- Cache configuration under `data/cache`.
- Session and timing-data validation.
- Driver-list extraction.
- Prepared session storage using CSV files and JSON metadata.
- Reliable fallback order for online deployment.

##  Explanation

"Role was data ingestion. I implemented the layer that receives Formula 1 session data through FastF1. It configures a local cache so repeated session requests do not need to download the same files again. The loader validates whether a session and its timing data were loaded correctly before passing information to the rest of the system. For deployment reliability, I also worked with prepared session storage, where validated telemetry and lap data are stored as CSV and JSON. The dashboard prefers prepared data, then attempts live FastF1 data, and transparently labels any fallback state."

## Key Technical Points

- FastF1 provides session, lap, telemetry, position, and event data.
- FastF1 cache improves speed and reduces repeated network downloads.
- Prepared data is different from demo data: it is saved, validated session output.
- Live public data can fail because it depends on external sources and network availability.

## Likely Questions and Answers

| Question | Short answer |
|---|---|
| What is FastF1? | FastF1 is a Python library that provides Formula 1 timing, session, lap, telemetry, position, weather, and event data in structured objects. |
| What is data ingestion? | It is the process of obtaining data from a source and bringing it into the project in a usable structured form. |
| Why is caching needed? | It avoids repeated downloads, reduces waiting time, and improves performance when the same session is requested again. |
| Where is the FastF1 cache stored? | The project configures it under `data/cache`. |
| What is a prepared session? | It is validated telemetry and lap data saved locally as CSV files and JSON metadata for stable later use. |
| Why does the deployed app prefer prepared data? | Cloud access to external FastF1 sources can be temporary or unreliable. Prepared data provides a reproducible and stable demonstration. |
| What is the difference between prepared data and demo data? | Prepared data comes from a real saved session. Demo data is only a clearly labelled fallback used when neither prepared nor live data is available. |
| What session types can be selected? | The UI supports qualifying, race, sprint, sprint qualifying, and practice session labels accepted by the application. |
| Why can FastF1 loading fail? | It may fail because of interrupted downloads, rate limits, changed sources, unavailable timing data, network restrictions, or stale cache files. |
| What validation is performed after loading? | The loader checks whether the session, timing data, and required lap information are available before analytics continue. |
| How do you obtain available drivers? | The session lap/timing data is used to extract driver identifiers for the selected event. |
| Why should the UI show source status? | It prevents misleading users. They should know whether they are viewing prepared data, live data, or labelled demonstration data. |
| Does FastF1 provide proprietary Formula 1 team telemetry? | No. This project uses publicly available data exposed through FastF1, not confidential team engineering systems. |

---

# 3. Avika Singh - Telemetry Processing

## Responsibility

Avika prepared raw telemetry for fair comparison:

- Cleaning telemetry channels and handling missing values.
- Converting time fields to numeric seconds when needed.
- Selecting each driver's fastest valid lap.
- Normalising brake and DRS-like fields into consistent values.
- Aligning driver traces by travelled distance.
- Interpolating signals onto a shared distance grid.

## Explanation

"Role was telemetry processing. Raw telemetry cannot be compared directly because drivers have different lap times, sample counts, and timestamps. I cleaned the required channels, handled missing data, selected the fastest valid lap for each driver, and converted relevant time values into numeric form. The most important step is distance-based alignment. Instead of comparing the same timestamp or array index, we compare both drivers at the same physical distance around the circuit. I use interpolation to estimate telemetry values on common distance points, which makes speed, throttle, brake, gear, and RPM comparisons meaningful."

## Key Technical Points

- Telemetry is time-series data with channels such as speed, throttle, brake, gear, RPM, X/Y position, and distance.
- Fastest-lap extraction gives a focused performance reference.
- Distance alignment makes corner-by-corner comparison valid.
- Interpolation estimates values between sampled points.

## Likely Questions and Answers

| Question | Short answer |
|---|---|
| What is telemetry processing? | It converts raw session signals into clean, comparable analysis-ready data. |
| Why is cleaning required? | Raw data may contain missing values, timing formats, incomplete laps, or inconsistent boolean and numeric fields. |
| What is a fastest lap? | The shortest valid timed lap recorded by a driver in the selected session. |
| Why compare fastest laps? | It gives a clear reference for analysing peak performance between drivers. |
| Why do you align telemetry by distance rather than time? | Distance represents the same physical location on the track. At the same distance, both drivers are approaching the same corner phase. |
| What is interpolation? | It estimates a value between known samples. Here it is used to place every driver's telemetry onto shared distance points. |
| What would be wrong with comparing the same array index? | Different laps can have different sample rates and lengths, so the same index may refer to different positions on the circuit. |
| What channels are processed? | Typical processed channels include distance, time, speed, throttle, brake, gear, RPM, DRS-ready values, and X/Y position. |
| How are missing values handled? | Required invalid or missing values are cleaned or excluded so they are not interpreted as real driving measurements. |
| Why convert time to numeric seconds? | Numeric seconds make timing comparison, delta calculation, statistics, and plotting easier and more reliable. |
| What is telemetry frequency in the UI? | It controls the density of sampled points used for chart rendering, balancing detail and dashboard performance. |
| Does interpolation create new real sensor readings? | No. It estimates comparison points between real samples; it does not claim that new measurements were captured. |
| What is the output of this stage? | Clean, distance-aligned DataFrames that analytics and Plotly visualization functions can use. |

---

# 4. Arsh Arun - Analytics and Machine Learning

## Responsibility

Arsh implemented the insight layer:

- Sector comparison and delta time.
- Braking-zone detection and summaries.
- Corner entry, apex, and exit performance indicators.
- Lap-time consistency measures.
- Tyre degradation trend estimation.
- KMeans lap clustering.
- IsolationForest anomaly detection.

##  Explanation

"Role was analytics and machine learning. I transformed aligned telemetry and lap data into performance insights. The system compares sectors, calculates delta time, identifies braking zones, and evaluates corner-related speed behaviour. It also measures lap-time consistency and estimates tyre degradation as a lap-time trend when usable data is available. For machine learning, KMeans groups laps with similar numeric features, while IsolationForest identifies unusual laps for review. These are unsupervised methods that help users find patterns; the project does not claim to predict race results or replace expert engineering judgement."

## Key Technical Points

- Delta time is cumulative elapsed-time difference between two aligned laps.
- Braking zones are sections where the brake signal is active.
- Consistency describes how repeatable lap times are.
- Tyre degradation is a descriptive trend, not a physics-based tyre model.
- KMeans groups similar laps; IsolationForest flags unusual observations.

## Likely Questions and Answers

| Question | Short answer |
|---|---|
| What is delta time? | It is the cumulative time gain or loss of one driver relative to another along the lap distance. |
| Why is delta time useful? | It shows where the gap grows or reduces, rather than showing only the final lap-time difference. |
| How are sectors analysed? | Sector times are extracted from lap data and compared between the selected drivers. |
| What is a braking zone? | A track section where the brake channel is active before or during a corner. |
| How is braking efficiency interpreted? | It is analysed descriptively through braking location, duration, speed change, and the resulting corner/exit behaviour. |
| What is corner entry, apex, and exit speed? | Entry speed is speed before turn-in, apex speed is near the slowest point, and exit speed is speed while accelerating away from the corner. |
| What does consistency mean? | It measures how repeatable a driver's lap times are, commonly using spread or standard deviation. |
| What is tyre degradation in this project? | A linear trend estimate of lap time against tyre life when sufficient valid lap data is available. |
| Is this a physical tyre simulation? | No. It is a descriptive performance trend, not a complete tyre-physics model. |
| What is KMeans? | KMeans is an unsupervised algorithm that groups observations, here laps, into clusters with similar features. |
| What features can be used for clustering? | Valid lap timing, sector values, tyre-life-related values, and other numeric lap features available in the dataset. |
| What is IsolationForest? | It is an unsupervised anomaly-detection algorithm that identifies observations with unusual feature patterns. |
| Does the project use supervised learning? | No. The implemented ML techniques are unsupervised because there are no labelled target categories for the laps. |
| Does the project predict race strategy or winners? | No. Predictive strategy, pit-stop simulation, driver scoring, and deep learning are future scope, not implemented claims. |
| Why should a human review ML anomalies? | An anomaly can be caused by traffic, weather, a pit stop, a yellow flag, an error, or genuine performance behaviour. Context is necessary. |

---

# 5. Kanishka - Frontend and Visualization

## Responsibility

Kanishka built the user-facing dashboard and visual communication layer:

- Streamlit controls for year, Grand Prix, session, driver selection, and telemetry frequency.
- Streamlit tabs for comparison, track, analytics, ML, and data views.
- Plotly telemetry charts for speed, throttle, brake, gear, RPM, and delta time.
- Track/racing-line overlays and speed heatmaps.
- Sector, lap-time, tyre, consistency, clustering, and anomaly visualizations.
- User messages for loading, source status, data limitations, and download actions.

##  Explanation

"Role was frontend and visualization. I used Streamlit to build the interactive dashboard where users select the year, Grand Prix, session, drivers, and telemetry frequency. Then I used Plotly to create interactive charts for speed, throttle, brake, gear, RPM, and delta time. I also implemented track-based views such as racing-line overlays and speed heatmaps, along with sector and analytics charts. Plotly allows users to hover, zoom, inspect legends, and compare traces easily. My goal was to convert complex Formula 1 telemetry into visuals that make driving differences understandable without requiring users to read raw data tables."

## Key Technical Points

- Streamlit creates the Python-based web interface.
- Plotly provides interactive charts with hover, zoom, legends, and downloadable visual output.
- The dashboard supports up to four selected drivers.
- A delta-time trace is most meaningful as a two-driver comparison.
- Clear source and error messages are part of good frontend design.

## Likely Questions and Answers

| Question | Short answer |
|---|---|
| What is the frontend of this project? | It is the Streamlit web interface that lets users choose data and view analysis results. |
| Why did you use Streamlit? | Streamlit lets us build a complete interactive web application directly in Python without separately creating a JavaScript frontend. |
| Why did you use Plotly? | Plotly creates professional interactive charts with hover, zoom, legends, pan controls, and responsive browser rendering. |
| What inputs can a user select? | The user can choose year, Grand Prix, session, telemetry frequency, and up to four drivers. |
| What telemetry charts are shown? | The core charts include speed, throttle, brake, gear, RPM, and delta time when a meaningful driver pair is selected. |
| What does a speed trace show? | It shows where drivers carry more or less speed, especially at corner entry, apex, and exit. |
| What does a throttle trace show? | It shows how early and how strongly a driver applies acceleration after a corner. |
| What does a brake trace show? | It shows braking location and brake application around corner approaches. |
| What does a racing-line overlay show? | It compares drivers' X/Y track positions to show how their paths differ through the circuit. |
| What is a speed heatmap? | It colours track-position points by speed so fast and slow sections of the circuit are visible. |
| Why are interactive charts better than static images here? | Users can hover for exact values, zoom into a corner, hide or show drivers, and inspect the trace they need. |
| Why limit selection to four drivers? | More traces can make a chart unreadable and increase rendering time; four offers useful comparison without excessive visual clutter. |
| How does the UI handle unavailable FastF1 data? | It displays clear status messages and can use prepared session data or clearly labelled demo data when necessary. |
| Is the deployed system a website or an app? | It is a web application: users open it in a browser, but it runs Python application logic through Streamlit. |
| What downloadable outputs are available? | The project supports CSV exports for data tables and an HTML comparison report workflow. |

---

# 6. Soumya Tandon - Testing, Documentation, and Deployment

## Responsibility

Soumya made the project usable, verifiable, and shareable:

- pytest tests for key processing and analytics behaviour.
- CSV export and HTML comparison report support.
- README, project structure, requirements, and presentation documentation.
- Git/GitHub repository workflow.
- Streamlit Community Cloud deployment.
- Deployment troubleshooting for dependency, import, cache, and FastF1 availability issues.

 Explanation

"Role was testing, documentation, and deployment. I helped ensure the project can be run, understood, and shared outside the development computer. The project uses pytest to validate key processing and analytics behaviour. I prepared documentation such as the README, requirements, project structure, setup instructions, and user workflow. I also worked on CSV and HTML report outputs. For deployment, the source code is hosted on GitHub and Streamlit Community Cloud runs the Python application online. I also handled common deployment concerns such as correct imports, compatible Python dependencies, data-source status, and cache-related errors."

## Key Technical Points

- Tests reduce the chance that refactoring breaks processing logic.
- README documents setup, commands, data paths, dashboard launch, and limitations.
- GitHub provides version history and connects to Streamlit Cloud.
- Streamlit Community Cloud redeploys from repository changes.
- No secrets or private team telemetry should be committed.

## Likely Questions and Answers

| Question | Short answer |
|---|---|
| Why is testing important? | Testing verifies that key functionality behaves as expected and detects regressions after code changes. |
| What is pytest? | pytest is a Python testing framework used to write and run automated tests. |
| What types of things are tested? | Focused processing, alignment, analytics, and expected output behaviour can be tested without manually checking every chart. |
| What is a regression? | A regression is when previously working behaviour breaks after a new change. |
| Why is documentation important? | Documentation lets another person install, run, understand, and evaluate the project without relying on the original developers. |
| What does the README contain? | It explains the project, dependencies, setup, dashboard command, CLI commands, architecture, exports, and limitations. |
| Why use GitHub? | GitHub stores version history, supports collaboration, and connects the repository to deployment platforms. |
| What is a commit? | A commit is a saved, named snapshot of project changes in Git. |
| What happens after pushing changes to GitHub? | Streamlit Cloud can detect the repository update and rebuild or redeploy the application. |
| What is Streamlit Community Cloud? | It is a hosting platform that runs a Streamlit Python app online from a GitHub repository. |
| Why is Python 3.12 recommended for deployment? | It has broad current library support and avoids using unreleased or unsupported package combinations. |
| What can cause deployment failure? | Missing dependencies, wrong file paths, import errors, incompatible Python versions, external data failure, or cache issues. |
| Why is `.gitignore` used? | It prevents local virtual environments, caches, logs, and other unnecessary or sensitive files from being committed. |
| What reports can the project export? | It can export tabular data as CSV and supports interactive HTML comparison report generation. |
| Is the deployed site guaranteed to receive live FastF1 data every time? | No. Public external data can be unavailable, which is why prepared session data and transparent source messages are important. |

---

# Cross-Team Questions: Every Member Should Know

| Question | Short answer |
|---|---|
| Explain the complete project flow. | The user selects an event and drivers, ingestion loads prepared or live data, processing cleans and aligns it, analytics computes insights, Plotly creates figures, and Streamlit displays/export results. |
| Why is this an AI/ML project? | It combines real-world data engineering, statistical analytics, time-series processing, KMeans clustering, and IsolationForest anomaly detection within an applied sports domain. |
| Is the dashboard using real Formula 1 data? | It uses real FastF1 data when live loading is available and real prepared session data for supported offline-ready sessions. Demo data, if used, is labelled clearly. |
| Why is prepared data useful? | It makes demonstrations and deployment more reproducible when public live data is unavailable. |
| What is the difference between a web app and a website? | A website mainly presents pages; this project is a web app because users choose inputs and the Python system dynamically processes and displays results. |
| Why is distance alignment a central design choice? | It compares drivers at the same physical track location, which is essential for meaningful corner-by-corner telemetry analysis. |
| Can the project replace a Formula 1 team's engineering system? | No. It is an educational and analytical platform using public data, not proprietary car sensors, simulations, or team tools. |
| What makes the solution scalable? | Clean module separation, reusable processing/visualization code, caching, prepared-data support, testing, and cloud deployment. |
| What is the most important deployment limitation? | Live FastF1 data depends on third-party sources and network conditions, so it cannot be guaranteed at every moment. |
| How can the project be improved? | Add more prepared sessions, corner labels, additional circuit markers, richer lap features, automated preparation jobs, and future predictive models after collecting suitable validated data. |
| How did the team work together? | Each member owned a module, but modules connect through the shared pipeline. The team tested integration from data loading through dashboard deployment. |
| What is the key result of the project? | It turns difficult raw Formula 1 telemetry into understandable interactive comparisons and analytical insights through a complete Python pipeline. |

---

 