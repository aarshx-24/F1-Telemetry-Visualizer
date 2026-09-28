"""Identify the executing build and environment without exposing diagnostics in the UI."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
from pathlib import Path
import platform
import subprocess


def log_runtime(root: Path, loader_source: str) -> str:
    """Return a source fingerprint suitable for separating Streamlit cache entries."""
    files = ("dashboard/app.py", "telemetry/ingestion/fastf1_session_loader.py")
    sources = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files
    }
    packages = {}
    for name in (
        "fastf1",
        "streamlit",
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "requests",
        "requests-cache",
        "urllib3",
        "pyarrow",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not installed"
    revision = "unavailable"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            revision = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    payload = {
        "revision": revision,
        "python": platform.python_version(),
        "packages": packages,
        "disk_sources": sources,
        "loader_import_source": loader_source,
    }
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.info("APP_RUNTIME %s", json.dumps(payload, sort_keys=True))
    if sources[files[1]] != loader_source:
        logger.error(
            "STALE_LOADER: imported source differs from disk; restart the server process to run the deployed loader."
        )
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
