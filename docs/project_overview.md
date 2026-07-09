# F1 Telemetry Visualizer - Complete Project Overview

## What This Platform Does

This project uses FastF1 to load Formula 1 timing, car telemetry, position data,
weather, and event metadata. It turns that raw data into reusable analysis objects,
then exposes the analysis through a CLI, generated HTML reports, and a Streamlit
dashboard.

## Core Telemetry Concepts

Speed traces reveal where a driver gains or loses speed across the lap.

Throttle traces show confidence and traction. Earlier full throttle on corner exit
usually means better rotation, better grip, or a more stable car.

Brake traces show braking points and braking duration. A later brake point is not
automatically better; the car must still reach the apex with enough rotation and
carry exit speed.

Delta time compares two laps over distance. If the delta line rises, the comparison
driver is losing time to the reference. If it falls, the comparison driver is
gaining time.

Racing lines use position coordinates. A wide entry, tight apex, and wide exit can
be compared against speed to understand whether a line actually produced lap time.

Tyre degradation is estimated from lap-time trend over a stint. A positive slope
means lap times are getting slower as the stint develops.

## Mathematical Ideas

Telemetry alignment uses interpolation. Two cars do not sample telemetry at exactly
the same distance points, so the platform builds a shared distance grid and
interpolates each channel onto that grid.

Delta time is computed as:

```text
comparison_time_at_distance - reference_time_at_distance
```

Braking-zone efficiency estimates speed drop per meter:

```text
(entry_speed - minimum_speed) / braking_distance
```

Tyre degradation uses a simple linear regression slope:

```text
lap_time = slope * lap_number + intercept
```

The ML tab uses clustering to group laps by timing-sector behavior and anomaly
detection to surface unusual laps.

## Professional Engineering Choices

The dashboard does not call FastF1 directly from plotting functions. It calls the
same ingestion, processing, analytics, and visualization layers used by the CLI.
That keeps the system reusable and testable.

The project keeps raw cache data, processed datasets, reports, source code, tests,
and documentation in separate folders. That mirrors how real analytics projects
avoid mixing provider cache, derived tables, and presentation artifacts.
