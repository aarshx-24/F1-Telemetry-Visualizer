"""Isolated FastF1 downloader. The parent enforces a whole-process deadline."""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from config.settings import build_settings
from telemetry.domain import ComparisonResult, SessionRequest
from telemetry.ingestion.fastf1_session_loader import FastF1SessionLoader
from telemetry.ingestion.processed_store import ProcessedTelemetryStore
from telemetry.processing import TelemetryExtractor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload")
    args = json.loads(parser.parse_args().payload)
    settings = build_settings(Path(args["project_root"]))
    loader = FastF1SessionLoader(settings)
    output = Path(args["output"])
    if args.get("action") == "calendar":
        fastf1 = loader._load_fastf1()
        loader._configure_cache(fastf1)
        schedule = fastf1.get_event_schedule(args["year"], include_testing=False)
        names = schedule["EventName"].dropna().astype(str).tolist()
        if not names:
            return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        pending = output.with_suffix(".tmp")
        pending.write_text(json.dumps(names), encoding="utf-8")
        pending.replace(output)
        return 0
    request = SessionRequest(**args["request"])
    session = loader.load_session(request, telemetry=True)
    extractor = TelemetryExtractor()
    selections = args.get("selections", {})
    drivers = list(selections) or extractor.available_drivers(session)
    laps = []
    for driver in drivers:
        try:
            lap = (
                extractor.extract_lap(
                    session, driver, int(selections[driver]), frequency=10
                )
                if driver in selections
                else extractor.extract_fastest_lap(session, driver, frequency=10)
            )
            laps.append(lap)
        except Exception:
            logging.exception("No usable telemetry for driver %s", driver)
    if not laps or (selections and len(laps) != len(selections)):
        return 1
    try:
        corners = pd.DataFrame(session.get_circuit_info().corners)
    except Exception:
        logging.exception("Circuit metadata unavailable")
        corners = pd.DataFrame()
    result = ComparisonResult(
        request, tuple(laps), pd.DataFrame(), extractor.sector_table(laps, session), ()
    )
    ProcessedTelemetryStore(output).save(
        result, extractor.lap_table(session), corners, frequency_hz=10
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception("FastF1 worker failed")
        raise SystemExit(1)
