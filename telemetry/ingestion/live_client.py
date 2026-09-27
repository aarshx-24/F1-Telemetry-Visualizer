"""Bounded process execution, cross-session locking and failed-request cooldown."""

from dataclasses import asdict
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from filelock import FileLock, Timeout

from config.settings import ProjectSettings
from telemetry.domain import SessionRequest

LOG = logging.getLogger(__name__)


class LiveSessionClient:
    def __init__(
        self, settings: ProjectSettings, *, timeout_seconds: int = 180
    ) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds
        self.root = settings.processed_data_dir / "downloaded"

    def fetch(
        self, request: SessionRequest, selections: dict[str, int] | None = None
    ) -> bool:
        return self._run(
            {
                "request": asdict(request),
                "selections": selections or {},
                "output": str(self.root),
            },
            self.timeout_seconds,
        )

    def calendar(self, year: int) -> list[str]:
        path = self.settings.cache_dir / f"schedule_{year}.json"
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if (
                    isinstance(cached, list)
                    and cached
                    and all(isinstance(v, str) for v in cached)
                ):
                    if time.time() - path.stat().st_mtime < 86400:
                        return cached
            except (OSError, ValueError):
                pass
        if self._run({"action": "calendar", "year": year, "output": str(path)}, 30):
            return json.loads(path.read_text(encoding="utf-8"))
        return []

    def _run(self, payload: dict, timeout: int) -> bool:
        import hashlib

        self.settings.ensure_directories()
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[
            :20
        ]
        failure = self.settings.cache_dir / f"failed_{key}.json"
        if failure.exists() and time.time() - failure.stat().st_mtime < 120:
            return False
        payload["project_root"] = str(self.settings.project_root)
        try:
            # All workers share FastF1's disk cache; serialize writers across visitors.
            with FileLock(str(self.settings.cache_dir / "download.lock"), timeout=0):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "telemetry.ingestion.worker",
                        json.dumps(payload),
                    ],
                    cwd=self.settings.project_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0:
                    failure.unlink(missing_ok=True)
                    return True
                LOG.error("FastF1 worker %s: %s", key, result.stderr[-8000:])
        except Timeout:
            return False
        except (subprocess.TimeoutExpired, OSError):
            LOG.exception(
                "FastF1 download %s exceeded its deadline or could not start", key
            )
        failure.write_text(json.dumps({"failed_at": time.time()}), encoding="utf-8")
        return False
