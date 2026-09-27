from dataclasses import dataclass
import logging
from typing import Protocol

import pandas as pd

from config.settings import ProjectSettings
from telemetry.domain import ComparisonResult, LapTelemetry, SessionRequest
from telemetry.ingestion.live_client import LiveSessionClient
from telemetry.ingestion.processed_store import (
    ProcessedSession,
    ProcessedTelemetryStore,
)

LOG = logging.getLogger(__name__)


class SessionClient(Protocol):
    def fetch(
        self, request: SessionRequest, selections: dict[str, int] | None = None
    ) -> bool: ...
    def calendar(self, year: int) -> list[str]: ...


@dataclass(frozen=True)
class SessionDataset:
    request: SessionRequest
    session: ProcessedSession
    laps: tuple[LapTelemetry, ...]
    source: str
    generated_at: str
    store: ProcessedTelemetryStore | None = None

    @property
    def drivers(self) -> list[str]:
        return sorted({lap.driver for lap in self.laps})


class SessionService:
    def __init__(
        self, settings: ProjectSettings, client: SessionClient | None = None
    ) -> None:
        self.client = client or LiveSessionClient(settings)
        self.stores = (
            (
                ProcessedTelemetryStore(settings.processed_data_dir / "downloaded"),
                "Downloaded FastF1 archive",
            ),
            (
                ProcessedTelemetryStore(settings.processed_data_dir / "prebuilt"),
                "Prepared FastF1 archive",
            ),
        )

    def catalog(self) -> list[SessionRequest]:
        return list(
            dict.fromkeys(
                request for store, _ in self.stores for request in store.list_requests()
            )
        )

    def _stored(
        self, request: SessionRequest, live: bool = False
    ) -> SessionDataset | None:
        for index, (store, source) in enumerate(self.stores):
            try:
                if store.contains(request):
                    laps = tuple(store.load_laps(request))
                    return SessionDataset(
                        request,
                        store.load_session(request),
                        laps,
                        "Fresh FastF1 download" if live and index == 0 else source,
                        store.generated_at(request),
                        store,
                    )
            except Exception:
                LOG.exception("Invalid stored session %s", request.label)
        return None

    def open(
        self, request: SessionRequest, *, refresh: bool = False
    ) -> SessionDataset | None:
        available = self._stored(request)
        if available is not None and not refresh:
            return available
        try:
            if self.client.fetch(request):
                return self._stored(request, live=True) or available
        except Exception:
            LOG.exception("Session acquisition unavailable: %s", request.label)
        return available

    def compare(
        self, dataset: SessionDataset, selections: dict[str, int]
    ) -> ComparisonResult | None:
        if dataset.store is None:
            return None
        try:
            return dataset.store.load_comparison(
                dataset.request, list(selections), selections=selections
            )
        except Exception:
            LOG.info("Selected laps are not yet stored")
        try:
            if self.client.fetch(dataset.request, selections):
                store = self.stores[0][0]
                return store.load_comparison(
                    dataset.request, list(selections), selections=selections
                )
        except Exception:
            LOG.exception("Selected lap download unavailable")
        return None


def provenance_table(table: pd.DataFrame, dataset: SessionDataset) -> pd.DataFrame:
    result = table.copy()
    result["DataSource"] = dataset.source
    result["Session"] = dataset.request.label
    result["GeneratedAt"] = dataset.generated_at
    return result
