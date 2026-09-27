"""Bounded process execution, cross-session locking and failed-request cooldown."""

from dataclasses import asdict
import hashlib
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

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
        return self._run(self._payload(request, selections), self.timeout_seconds)

    def _payload(
        self, request: SessionRequest, selections: dict[str, int] | None = None
    ) -> dict:
        return {
            "request": asdict(request),
            "selections": selections or {},
            "output": str(self.root),
        }

    def _failure_path(self, payload: dict) -> Path:
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[
            :20
        ]
        return self.settings.cache_dir / f"failed_{key}.json"

    def failure_message(
        self, request: SessionRequest, selections: dict[str, int] | None = None
    ) -> str:
        """Return a safe status, never worker stderr or private server paths."""
        try:
            status = json.loads(
                self._failure_path(self._payload(request, selections)).read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, ValueError):
            return "No usable session archive is available. The server logs contain the download details."
        messages = {
            "busy": "Another session is downloading. Retry shortly; this does not mean this event is unavailable.",
            "timeout": "The download exceeded the server time limit. A cold download may take longer; a prepared archive can avoid this download.",
            "start_failed": "The server could not start or access the downloader. The app owner needs to inspect the server logs.",
            "worker_failed": "The download process ended without a usable session. The server logs contain its exit code and FastF1 diagnostics.",
        }
        message = messages.get(
            status.get("category"),
            "The last download failed. The server logs contain the details.",
        )
        remaining = max(
            0,
            int(
                status.get("failed_at", 0)
                + status.get("retry_after", 120)
                - time.time()
            ),
        )
        if remaining:
            message += f" Automatic retry cooldown: {remaining} seconds remaining."
        return message

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
        self.settings.ensure_directories()
        failure = self._failure_path(payload)
        key = failure.stem
        if failure.exists():
            try:
                status = json.loads(failure.read_text(encoding="utf-8"))
                if time.time() - status["failed_at"] < status.get("retry_after", 120):
                    return False
            except (OSError, ValueError, KeyError, TypeError):
                LOG.warning("Ignoring invalid download status %s", key)
        payload = dict(payload)
        payload["project_root"] = str(self.settings.project_root)
        category, retry_after = "worker_failed", 120
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
                LOG.error(
                    "FastF1 worker %s exit=%s: %s",
                    key,
                    result.returncode,
                    result.stderr[-8000:],
                )
        except Timeout:
            category, retry_after = "busy", 3
        except subprocess.TimeoutExpired:
            category = "timeout"
            LOG.exception(
                "FastF1 download %s exceeded its %s-second deadline", key, timeout
            )
        except OSError:
            category = "start_failed"
            LOG.exception("FastF1 download %s could not start or access its files", key)
        pending = failure.with_name(f"{failure.stem}_{uuid4().hex}.tmp")
        pending.write_text(
            json.dumps(
                {
                    "failed_at": time.time(),
                    "category": category,
                    "retry_after": retry_after,
                }
            ),
            encoding="utf-8",
        )
        pending.replace(failure)
        return False
