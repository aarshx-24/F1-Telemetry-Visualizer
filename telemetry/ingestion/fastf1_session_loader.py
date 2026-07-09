from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any

from config.settings import ProjectSettings
from telemetry.domain import SessionRequest, SessionSummary
from telemetry.ingestion.calendar import COMMON_GRAND_PRIX_NAMES


class FastF1NotInstalledError(RuntimeError):
    """Raised when FastF1 is required but is not installed."""


class FastF1DataLoadError(RuntimeError):
    """Raised when FastF1 returns a session without required data loaded."""


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

        session = fastf1.get_session(
            request.year,
            request.grand_prix,
            request.session_type,
        )
        try:
            session.load(
                laps=True,
                telemetry=telemetry,
                weather=True,
                messages=False,
            )
            self._validate_loaded_session(session, request, telemetry=telemetry)
        except Exception as exc:
            raise FastF1DataLoadError(
                f"FastF1 could not fully load {request.label}. "
                "This is usually caused by an interrupted data download, blocked network, "
                "or a stale Streamlit cache. Clear the dashboard cache and reload the session."
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
        except Exception:
            return COMMON_GRAND_PRIX_NAMES

        if "EventName" not in schedule:
            return COMMON_GRAND_PRIX_NAMES

        events = [
            str(event)
            for event in schedule["EventName"].dropna().tolist()
            if str(event).strip()
        ]
        return events or COMMON_GRAND_PRIX_NAMES

    def _configure_cache(self, fastf1: ModuleType) -> None:
        self._settings.ensure_directories()
        self._configure_logging(fastf1)
        fastf1.Cache.enable_cache(str(self._settings.cache_dir))

    @staticmethod
    def _configure_logging(fastf1: ModuleType) -> None:
        set_log_level = getattr(fastf1, "set_log_level", None)
        if set_log_level is not None:
            set_log_level("ERROR")

        for logger_name in ("fastf1", "requests_cache", "urllib3"):
            logging.getLogger(logger_name).setLevel(logging.ERROR)

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
            _ = session.car_data
            _ = session.pos_data

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
