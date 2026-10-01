import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from config.settings import build_settings
from telemetry.domain import SessionRequest
from telemetry.ingestion.fastf1_session_loader import (
    FastF1DataLoadError,
    FastF1SessionLoader,
)
from telemetry.ingestion.resilient_session_loader import (
    PRESENTATION_GRAND_PRIX_NAMES,
    ResilientSessionLoader,
)


@pytest.fixture(autouse=True)
def isolated_app_cache():
    st.cache_resource.clear()
    st.cache_data.clear()
    yield
    st.cache_resource.clear()
    st.cache_data.clear()


def test_live_failure_uses_real_demo_data_and_keeps_driver_control_available(
    monkeypatch,
):
    monkeypatch.setattr(
        FastF1SessionLoader,
        "list_grand_prix",
        lambda self, year: ["Italian Grand Prix"],
    )
    load = Mock(side_effect=FastF1DataLoadError("Diagnostic reference: test"))
    monkeypatch.setattr(FastF1SessionLoader, "load_session", load)
    app = AppTest.from_file("dashboard/app.py").run(timeout=20)
    assert not app.exception
    assert app.multiselect[0].label == "Drivers"
    assert not app.multiselect[0].disabled
    assert {"VER", "LEC"}.issubset(app.multiselect[0].options)
    assert any("Demonstration Mode" in warning.value for warning in app.warning)
    assert app.get("plotly_chart")
    app.run(timeout=20)
    assert load.call_count == 1


def test_year_change_resets_event_and_drivers_and_uses_distinct_cache_entries(
    monkeypatch,
):
    events = {
        2022: ["Italian Grand Prix", "French Grand Prix"],
        2023: ["Italian Grand Prix", "Las Vegas Grand Prix"],
        2024: ["Italian Grand Prix"],
    }
    monkeypatch.setattr(
        FastF1SessionLoader, "list_grand_prix", lambda self, year: events[year]
    )
    calls = []

    def load(self, request, **kwargs):
        calls.append(request)
        driver = "VET" if request.year == 2022 else "LAW"
        # One driver stops before plotting; real multi-driver behavior is separately probed.
        return SimpleNamespace(results=pd.DataFrame({"Abbreviation": [driver]}))

    monkeypatch.setattr(FastF1SessionLoader, "load_session", load)
    app = AppTest.from_file("dashboard/app.py").run()
    app.number_input[0].set_value(2022).run()
    app.selectbox[0].set_value("French Grand Prix").run()
    assert app.multiselect[0].value == ["VET"]
    app.number_input[0].set_value(2023).run()
    assert app.selectbox[0].value == "Italian Grand Prix"
    assert "French Grand Prix" not in app.selectbox[0].options
    assert app.multiselect[0].value == ["LAW"]
    assert not app.multiselect[0].disabled
    assert calls[-1] == SessionRequest(2023, "Italian Grand Prix", "Q")
    count = len(calls)
    app.run()
    assert len(calls) == count
    app.number_input[0].set_value(2022).run()
    assert app.multiselect[0].value == ["VET"]
    assert not app.exception


def test_loader_preserves_original_exception_and_traceback(
    tmp_path, monkeypatch, caplog
):
    loader = FastF1SessionLoader(build_settings(tmp_path))
    root_error = ConnectionError("simulated transport failure")
    api = Mock(__version__="test")
    api.get_session.side_effect = root_error
    monkeypatch.setattr(loader, "_load_fastf1", lambda: api)
    monkeypatch.setattr(loader, "_configure_cache", lambda _: None)
    with caplog.at_level(logging.INFO), pytest.raises(FastF1DataLoadError) as error:
        loader.load_session(SessionRequest(2023, "Italian Grand Prix", "Q"))
    assert error.value.__cause__ is root_error
    assert any(
        record.exc_info and record.exc_info[1] is root_error
        for record in caplog.records
    )
    api.get_session.assert_called_once_with(2023, "Italian Grand Prix", "Q")


def test_partial_session_is_rejected_before_caching():
    session = SimpleNamespace(
        laps=pd.DataFrame({"Driver": ["VER"]}), car_data={}, pos_data={}
    )
    with pytest.raises(FastF1DataLoadError, match="car_data"):
        FastF1SessionLoader._validate_loaded_session(
            session, SessionRequest(2023, "Italian Grand Prix", "Q"), telemetry=True
        )


def test_canonical_event_cannot_fuzzy_match_another_event(tmp_path, monkeypatch):
    loader = FastF1SessionLoader(build_settings(tmp_path))
    session = SimpleNamespace(event={"EventName": "Belgian Grand Prix"}, load=Mock())
    api = Mock()
    api.get_session.return_value = session
    monkeypatch.setattr(loader, "_load_fastf1", lambda: api)
    monkeypatch.setattr(loader, "_configure_cache", lambda _: None)
    with pytest.raises(FastF1DataLoadError) as exc:
        loader.load_session(SessionRequest(2023, "French Grand Prix", "Q"))
    assert isinstance(exc.value.__cause__, ValueError)
    session.load.assert_not_called()


def test_fastf1_soft_failure_tracebacks_are_not_suppressed():
    api = Mock()
    FastF1SessionLoader._configure_logging(api)
    api.set_log_level.assert_called_once_with("DEBUG")
    assert logging.getLogger("fastf1").isEnabledFor(logging.DEBUG)


@pytest.mark.parametrize("schedule", [pd.DataFrame(), pd.DataFrame({"EventName": []})])
def test_missing_calendar_never_offers_unverified_events(
    tmp_path, monkeypatch, schedule
):
    loader = FastF1SessionLoader(build_settings(tmp_path))
    api = Mock()
    api.get_event_schedule.return_value = schedule
    monkeypatch.setattr(loader, "_load_fastf1", lambda: api)
    monkeypatch.setattr(loader, "_configure_cache", lambda _: None)
    with pytest.raises(FastF1DataLoadError):
        loader.list_grand_prix(2023)
    api.get_event_schedule.assert_called_once_with(2023, include_testing=False)


def test_calendar_network_failure_preserves_cause(tmp_path, monkeypatch):
    loader = FastF1SessionLoader(build_settings(tmp_path))
    api = Mock()
    cause = ConnectionError("schedule unavailable")
    api.get_event_schedule.side_effect = cause
    monkeypatch.setattr(loader, "_load_fastf1", lambda: api)
    monkeypatch.setattr(loader, "_configure_cache", lambda _: None)
    with pytest.raises(FastF1DataLoadError) as error:
        loader.list_grand_prix(2023)
    assert error.value.__cause__ is cause


def test_calendar_failure_uses_presentation_options_and_demo_data(monkeypatch):
    monkeypatch.setattr(
        FastF1SessionLoader,
        "list_grand_prix",
        Mock(side_effect=FastF1DataLoadError("unavailable")),
    )
    monkeypatch.setattr(
        FastF1SessionLoader,
        "load_session",
        Mock(side_effect=FastF1DataLoadError("session unavailable")),
    )
    app = AppTest.from_file("dashboard/app.py").run(timeout=20)
    assert not app.exception
    assert not app.selectbox[0].disabled
    assert "Italian Grand Prix" in app.selectbox[0].options
    assert set(PRESENTATION_GRAND_PRIX_NAMES) == set(app.selectbox[0].options)
    assert not app.multiselect[0].disabled
    assert app.multiselect[0].options


@pytest.mark.parametrize("session_type", ["Q", "R", "FP1", "FP2", "FP3", "SQ", "S"])
def test_demo_fixture_supports_every_session_selector_state(monkeypatch, session_type):
    loader = ResilientSessionLoader(build_settings(Path.cwd()))
    monkeypatch.setattr(
        FastF1SessionLoader,
        "load_session",
        Mock(side_effect=FastF1DataLoadError("network unavailable")),
    )
    requested = SessionRequest(2025, "Italian Grand Prix", session_type)
    loaded = loader.load_session(requested)
    assert loaded.source == "fallback"
    assert loaded.requested == requested
    assert loaded.source_request == SessionRequest(2024, "Bahrain Grand Prix", "Q")
    assert {"VER", "LEC"}.issubset(loaded.session.drivers)
    assert not loaded.session.laps.empty


def test_presentation_calendar_never_uses_deprecated_hardcoded_events(monkeypatch):
    loader = ResilientSessionLoader(build_settings(Path.cwd()))
    monkeypatch.setattr(
        FastF1SessionLoader,
        "list_grand_prix",
        Mock(side_effect=FastF1DataLoadError("calendar unavailable")),
    )
    options, is_live = loader.list_grand_prix(2024)
    assert not is_live
    assert options == PRESENTATION_GRAND_PRIX_NAMES
    assert "70th Anniversary Grand Prix" not in options


def test_load_arguments_and_validation_order(tmp_path, monkeypatch):
    loader = FastF1SessionLoader(build_settings(tmp_path))
    events = []

    class Session:
        def __init__(self) -> None:
            self.event = {"EventName": "Italian Grand Prix"}
            self.drivers = ["VER"]
            self.car_data = {"VER": pd.DataFrame({"Speed": [100]})}
            self.pos_data = {"VER": pd.DataFrame({"X": [0]})}

        def load(self, **kwargs):
            assert kwargs == {
                "laps": True,
                "telemetry": True,
                "weather": True,
                "messages": False,
            }
            events.append("load")

        @property
        def laps(self):
            assert events[0] == "load"
            events.append("validate")
            return pd.DataFrame({"Driver": ["VER"]})

    api = Mock()
    api.get_session.return_value = Session()
    monkeypatch.setattr(loader, "_load_fastf1", lambda: api)
    monkeypatch.setattr(loader, "_configure_cache", lambda _: None)
    loader.load_session(SessionRequest(2023, "Italian Grand Prix", "Q"))
    assert events[:2] == ["load", "validate"]
