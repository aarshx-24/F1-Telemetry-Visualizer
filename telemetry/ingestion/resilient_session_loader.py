"""Live-first ingestion with an explicitly labelled local real-data fallback."""

from __future__ import annotations

import logging

from config.settings import ProjectSettings
from telemetry.domain import LoadedSession, SessionRequest
from telemetry.ingestion.demo_session import DEMO_SOURCE_REQUEST, DemoSessionLoader
from telemetry.ingestion.fastf1_session_loader import FastF1SessionLoader

LOG = logging.getLogger(__name__)

# Used only when a calendar cannot be obtained. These names are controls for a
# demonstration request; displayed telemetry is always labelled with its source.
PRESENTATION_GRAND_PRIX_NAMES = [
    "Australian Grand Prix",
    "Bahrain Grand Prix",
    "Saudi Arabian Grand Prix",
    "Japanese Grand Prix",
    "Chinese Grand Prix",
    "Miami Grand Prix",
    "Emilia Romagna Grand Prix",
    "Monaco Grand Prix",
    "Spanish Grand Prix",
    "Canadian Grand Prix",
    "Austrian Grand Prix",
    "British Grand Prix",
    "Hungarian Grand Prix",
    "Belgian Grand Prix",
    "Dutch Grand Prix",
    "Italian Grand Prix",
    "Azerbaijan Grand Prix",
    "Singapore Grand Prix",
    "United States Grand Prix",
    "Mexico City Grand Prix",
    "Sao Paulo Grand Prix",
    "Las Vegas Grand Prix",
    "Qatar Grand Prix",
    "Abu Dhabi Grand Prix",
]


class ResilientSessionLoader:
    """Preserve a fully functional dashboard when live timing is unavailable."""

    def __init__(self, settings: ProjectSettings) -> None:
        self._live = FastF1SessionLoader(settings)
        self._demo = DemoSessionLoader(settings.project_root)

    def load_session(self, request: SessionRequest) -> LoadedSession:
        try:
            return LoadedSession(
                session=self._live.load_session(request, telemetry=True),
                requested=request,
                source="live",
                source_request=request,
            )
        except Exception as exc:
            LOG.exception(
                "Live FastF1 load failed for %s; activating real-data demonstration fixture",
                request.label,
            )
            demo = self._demo.load()
            return LoadedSession(
                session=demo,
                requested=request,
                source="fallback",
                source_request=DEMO_SOURCE_REQUEST,
                error=f"{type(exc).__name__}: {exc}",
            )

    def list_grand_prix(self, year: int) -> tuple[list[str], bool]:
        try:
            return self._live.list_grand_prix(year), True
        except Exception:
            LOG.exception(
                "Live FastF1 calendar failed for %s; retaining presentation selector options",
                year,
            )
            return PRESENTATION_GRAND_PRIX_NAMES, False
