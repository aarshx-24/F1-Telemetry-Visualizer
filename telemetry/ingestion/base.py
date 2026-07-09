from __future__ import annotations

from typing import Any, Protocol

from telemetry.domain import SessionRequest, SessionSummary


class SessionLoader(Protocol):
    """Interface for objects that load F1 session data."""

    def load_session(self, request: SessionRequest, *, telemetry: bool = True) -> Any:
        """Load and return a provider-specific session object."""

    def load_session_summary(self, request: SessionRequest) -> SessionSummary:
        """Load enough data to produce a session summary."""
