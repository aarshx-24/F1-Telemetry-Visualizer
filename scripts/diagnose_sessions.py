"""Opt-in real-data diagnostics; never part of the offline test suite."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import platform
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["standalone", "transition", "fresh"], required=True
    )
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--event", default="Italian Grand Prix")
    parser.add_argument("--fresh-cache", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "logs" / "year-diagnostics"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = str(time.time_ns())
    log_path = folder / f"{args.mode}_{args.year}_{stamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    import fastf1
    import streamlit as st

    logging.info(
        "Python=%s executable=%s FastF1=%s Streamlit=%s",
        platform.python_version(),
        sys.executable,
        fastf1.__version__,
        st.__version__,
    )
    rows = []
    if args.mode == "standalone":
        cache = (
            ROOT / "data" / "cache"
            if not args.fresh_cache
            else folder / f"fresh_cache_{stamp}"
        )
        cache.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(cache))
        fastf1.set_log_level("DEBUG")
        try:
            event = fastf1.get_event(args.year, args.event)
            session = event.get_session("Q")
            logging.info(
                "Resolved event=%s round=%s session=%s api_path=%s",
                event.EventName,
                event.RoundNumber,
                session.name,
                session.api_path,
            )
            session.load(laps=True, telemetry=True, weather=True, messages=False)
            lap = session.laps.pick_drivers("VER").pick_fastest()
            telemetry = lap.get_telemetry()
            rows.append(
                {
                    "year": args.year,
                    "event": str(event.EventName),
                    "round": int(event.RoundNumber),
                    "laps": len(session.laps),
                    "drivers": len(session.drivers),
                    "telemetry_rows": len(telemetry),
                    "success": True,
                }
            )
        except Exception as exc:
            logging.exception("STANDALONE FAILURE")
            rows.append(
                {
                    "year": args.year,
                    "success": False,
                    "exception": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )
    else:
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        from telemetry.ingestion.fastf1_session_loader import FastF1SessionLoader

        original = FastF1SessionLoader.load_session

        def observed(self, request, **kwargs):
            logging.info("APP REQUEST %s", request)
            try:
                result = original(self, request, **kwargs)
                logging.info(
                    "APP LOADED %s round=%s laps=%s",
                    request.label,
                    result.event.RoundNumber,
                    len(result.laps),
                )
                return result
            except Exception:
                logging.exception("APP FULL EXCEPTION CHAIN for %s", request.label)
                raise

        source = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
        start = 2022 if args.mode == "transition" else args.year
        source = source.replace(
            "ROOT = Path(__file__).resolve().parents[1]", f"ROOT = Path({str(ROOT)!r})"
        )
        source = source.replace("value=2024", f"value={start}")
        st.cache_resource.clear()
        st.cache_data.clear()
        with patch.object(FastF1SessionLoader, "load_session", observed):
            app = AppTest.from_string(source, default_timeout=300).run()
            years = [start, 2023, 2022, 2024] if args.mode == "transition" else [start]
            for index, year in enumerate(years):
                if index:
                    next(
                        item for item in app.number_input if item.label == "Year"
                    ).set_value(year).run()
                driver_controls = [
                    item for item in app.multiselect if item.label == "Drivers"
                ]
                row = {
                    "year": year,
                    "errors": [item.value for item in app.error],
                    "exceptions": [item.message for item in app.exception],
                    "charts": len(app.get("plotly_chart")),
                    "drivers": driver_controls[0].options if driver_controls else [],
                    "driver_disabled": driver_controls[0].disabled
                    if driver_controls
                    else None,
                    "state": repr(app.session_state.filtered_state),
                }
                rows.append(row)
                logging.info("APP RESULT %s", json.dumps(row))
    output = log_path.with_suffix(".json")
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("RESULT_FILE", output, flush=True)


if __name__ == "__main__":
    main()
