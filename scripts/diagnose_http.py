"""Run the exact same bounded HTTP diagnostic on a local machine or Cloud."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telemetry.ingestion.http_diagnostics import PREFIX, run_probe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--years", nargs="+", type=int, choices=(2022, 2023, 2024), default=[2024]
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", args.run_id):
        parser.error("run-id must contain 1-48 letters, digits, underscores or hyphens")
    folder = ROOT / "logs/http-diagnostics" / args.run_id
    # Never reuse a diagnostic cache and mislabel it as fresh.
    if folder.exists():
        parser.error("run-id already exists; choose a new run-id")
    try:
        run_probe(ROOT, folder, tuple(dict.fromkeys(args.years)), args.run_id)
    except Exception as exc:
        import json

        print(
            PREFIX
            + json.dumps(
                {"event": "probe_failed", "exception_type": type(exc).__name__}
            ),
            flush=True,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
