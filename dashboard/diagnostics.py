"""Owner-enabled diagnostic launcher; no public widgets, query parameters or output."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
from collections.abc import Mapping
from pathlib import Path

from telemetry.ingestion.http_diagnostics import PREFIX

LOG = logging.getLogger(__name__)


def start_owner_diagnostics(root: Path, config: Mapping) -> None:
    if config.get("enabled") is not True:
        return
    run_id = str(config.get("run_id", ""))
    years = config.get("years", [2024])
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", run_id) or not isinstance(
        years, (list, tuple)
    ):
        LOG.warning("HTTP diagnostics configuration rejected; check the owner runbook")
        return
    if (
        not years
        or len(years) > 3
        or any(
            type(year) is not int or year not in (2022, 2023, 2024) for year in years
        )
    ):
        LOG.warning("HTTP diagnostic years must be a list drawn from 2022, 2023, 2024")
        return
    # The owner chooses a new id for each run. Exclusive creation makes reruns
    # and concurrent visitors unable to create repeated diagnostic jobs.
    folder = root / "logs/http-diagnostics"
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / f"{run_id}.started"
    try:
        with marker.open("x", encoding="utf-8") as handle:
            handle.write("Owner-enabled diagnostic run\n")
    except FileExistsError:
        return
    worker = threading.Thread(
        target=_run,
        args=(root, run_id, years),
        daemon=True,
        name="owner-http-diagnostics",
    )
    worker.start()


def _run(root: Path, run_id: str, years: list[int]) -> None:
    print(PREFIX + json.dumps({"event": "worker_start", "run_id": run_id}), flush=True)
    command = [
        sys.executable,
        "-u",
        "scripts/diagnose_http.py",
        "--run-id",
        run_id,
        "--years",
        *map(str, years),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        deadline = threading.Timer(900, process.kill)
        deadline.daemon = True
        deadline.start()
        try:
            for line in process.stdout:
                # Forward only the worker's sanitized structured records, never
                # arbitrary dependency stderr (which may contain credentials).
                if line.startswith(PREFIX) and len(line) < 16384:
                    try:
                        record = json.loads(line[len(PREFIX) :])
                        print(PREFIX + json.dumps(record), flush=True)
                    except ValueError:
                        pass
            code = process.wait()
        finally:
            deadline.cancel()
            process.stdout.close()
        print(
            PREFIX
            + json.dumps(
                {"event": "worker_exit", "run_id": run_id, "returncode": code}
            ),
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic worker must not crash the app.
        print(
            PREFIX
            + json.dumps(
                {
                    "event": "worker_failed",
                    "run_id": run_id,
                    "exception_type": type(exc).__name__,
                }
            ),
            flush=True,
        )
