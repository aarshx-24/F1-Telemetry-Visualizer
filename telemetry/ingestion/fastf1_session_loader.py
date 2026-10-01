from __future__ import annotations

import hashlib
import importlib
import logging
import time
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

from config.settings import ProjectSettings
from telemetry.domain import SessionRequest, SessionSummary
from telemetry.ingestion.calendar import COMMON_GRAND_PRIX_NAMES

LOG = logging.getLogger(__name__)
LOADER_SOURCE_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class FastF1NotInstalledError(RuntimeError):
    """Raised when FastF1 is required but is not installed."""


class FastF1DataLoadError(RuntimeError):
    """Raised when FastF1 returns a session without required data loaded."""

    def __init__(self, message: str, *, partial_session: Any = None) -> None:
        super().__init__(message)
        self.partial_session = partial_session


class FastF1SessionLoader:
    """FastF1-backed implementation of the session ingestion boundary."""

    def __init__(self, settings: ProjectSettings) -> None:
        self._settings = settings

    @property
    def settings(self) -> ProjectSettings:
        return self._settings

    def load_session(self, request: SessionRequest, *, telemetry: bool = True) -> Any:
        fastf1 = self._load_fastf1()
        self._configure_cache(fastf1)

        reference = uuid4().hex[:12]
        started = time.monotonic()
        session = None
        try:
            LOG.info(
                "Loader source at import=%s disk=%s cache=%s",
                LOADER_SOURCE_SHA,
                hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                self._settings.cache_dir,
            )
            LOG.info(
                "Session load %s: year=%s event=%s session=%s FastF1=%s",
                reference,
                request.year,
                request.grand_prix,
                request.session_type,
                getattr(fastf1, "__version__", "unknown"),
            )
            # FastF1 resolves the event against this request's year, not a stored round.
            session = fastf1.get_session(
                request.year, request.grand_prix, request.session_type
            )
            if (
                request.grand_prix in COMMON_GRAND_PRIX_NAMES
                and _safe_get(session.event, "EventName", None) != request.grand_prix
            ):
                raise ValueError(
                    f"{request.grand_prix} did not resolve exactly in the {request.year} schedule."
                )
            LOG.info(
                "Session resolved %s: event=%s round=%s date=%s api_path=%s",
                reference,
                _safe_get(session.event, "EventName", "unknown"),
                _safe_get(session.event, "RoundNumber", "unknown"),
                getattr(session, "date", "unknown"),
                getattr(session, "api_path", "unknown"),
            )
            session.load(
                laps=True,
                telemetry=telemetry,
                weather=True,
                messages=False,
            )
            self._validate_loaded_session(session, request, telemetry=telemetry)
            LOG.info(
                "Session loaded [%s] %s laps=%s drivers=%s elapsed=%.2fs",
                reference,
                request.label,
                len(session.laps),
                len(session.drivers),
                time.monotonic() - started,
            )
        except Exception as exc:
            LOG.exception("Session load failed [%s] %s", reference, request.label)
            raise FastF1DataLoadError(
                f"FastF1 could not fully load {request.label}. "
                f"Server diagnostic reference: {reference}.",
                partial_session=session,
            ) from exc
        return session

    def load_session_summary(self, request: SessionRequest) -> SessionSummary:
        session = self.load_session(request, telemetry=False)

        event = getattr(session, "event", {})
        laps = getattr(session, "laps", [])
        drivers = getattr(session, "drivers", [])

        return SessionSummary(
            request=request,
            event_name=str(_safe_get(event, "EventName", request.grand_prix)),
            session_name=str(getattr(session, "name", request.session_type)),
            date=str(getattr(session, "date", "unknown")),
            circuit_name=str(_safe_get(event, "Location", "unknown")),
            driver_count=len(drivers),
            lap_count=len(laps),
            cache_path=str(self._settings.cache_dir),
        )

    def list_grand_prix(self, year: int) -> list[str]:
        fastf1 = self._load_fastf1()
        self._configure_cache(fastf1)

        try:
            schedule = fastf1.get_event_schedule(year, include_testing=False)
        except Exception as exc:
            LOG.exception("Could not load the %s schedule", year)
            raise FastF1DataLoadError(
                f"The verified {year} calendar could not be loaded."
            ) from exc

        if "EventName" not in schedule:
            raise FastF1DataLoadError(f"The {year} calendar has no event names.")

        events = [
            str(event)
            for event in schedule["EventName"].dropna().tolist()
            if str(event).strip()
        ]
        if not events:
            raise FastF1DataLoadError(f"The {year} calendar is empty.")
        return events

    def _configure_cache(self, fastf1: ModuleType) -> None:
        self._settings.ensure_directories()
        self._configure_logging(fastf1)
        fastf1.Cache.enable_cache(str(self._settings.cache_dir))

    @staticmethod
    def _configure_logging(fastf1: ModuleType) -> None:
        set_log_level = getattr(fastf1, "set_log_level", None)
        if set_log_level is not None:
            # FastF1 soft-failure tracebacks are DEBUG records, not ERROR records.
            set_log_level("DEBUG")

        logging.getLogger("fastf1").setLevel(logging.DEBUG)
        for handler in logging.getLogger("fastf1").handlers:
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
        LOG.setLevel(logging.INFO)
        if not LOG.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            LOG.addHandler(handler)
        for logger_name in ("requests_cache", "urllib3"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    @staticmethod
    def _validate_loaded_session(
        session: Any,
        request: SessionRequest,
        *,
        telemetry: bool,
    ) -> None:
        laps = session.laps
        if laps.empty:
            raise FastF1DataLoadError(f"No laps were loaded for {request.label}.")

        if telemetry:
            for channel in ("car_data", "pos_data"):
                values = getattr(session, channel)
                if not values or not any(not frame.empty for frame in values.values()):
                    raise FastF1DataLoadError(
                        f"No {channel} samples were loaded for {request.label}."
                    )

    @staticmethod
    def _load_fastf1() -> ModuleType:
        try:
            return importlib.import_module("fastf1")
        except ModuleNotFoundError as exc:
            raise FastF1NotInstalledError(
                "FastF1 is not installed in the active Python environment."
            ) from exc


def _safe_get(mapping: Any, key: str, default: Any) -> Any:
    getter = getattr(mapping, "get", None)
    if getter is None:
        return default
    return getter(key, default)
