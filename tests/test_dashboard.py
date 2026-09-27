from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from telemetry.domain import SessionRequest


def test_prepared_dashboard_needs_no_download(monkeypatch):
    request = SessionRequest(2024, "Italian Grand Prix", "Q")
    monkeypatch.setattr(
        "telemetry.application.sessions.SessionService.catalog", lambda self: [request]
    )
    fetch = Mock(side_effect=AssertionError("Prepared sessions must not download"))
    monkeypatch.setattr(
        "telemetry.ingestion.live_client.LiveSessionClient.fetch", fetch
    )
    app = AppTest.from_file("dashboard/app.py", default_timeout=120).run()
    assert not app.exception
    assert not app.error
    assert not app.info
    assert len(app.get("plotly_chart")) >= 12
    for selector in app.selectbox:
        if selector.label.endswith(" lap"):
            assert all("(saved)" in option for option in selector.options)
    fetch.assert_not_called()
    drivers = next(item for item in app.multiselect if item.label == "Drivers")
    drivers.set_value(["VER", "LEC", "HAM"]).run()
    next(item for item in app.selectbox if item.label == "Reference driver").set_value(
        "LEC"
    ).run()
    assert not app.exception
    assert not app.info
    app.radio[0].set_value("Demonstration").run()
    assert not app.exception
    assert any("SYNTHETIC DEMONSTRATION" in c.value for c in app.caption)


def test_unavailable_session_has_status_not_traceback(monkeypatch):
    monkeypatch.setattr(
        "telemetry.application.sessions.SessionService.open",
        lambda *args, **kwargs: None,
    )
    app = AppTest.from_file("dashboard/app.py", default_timeout=120).run()
    assert not app.exception
    assert not app.error
    assert any(
        "No synthetic data has been substituted" in item.value for item in app.info
    )


def test_online_lap_failure_can_return_to_saved_laps(monkeypatch):
    request = SessionRequest(2024, "Italian Grand Prix", "Q")
    monkeypatch.setattr(
        "telemetry.application.sessions.SessionService.catalog", lambda self: [request]
    )
    fetch = Mock(return_value=False)
    monkeypatch.setattr(
        "telemetry.ingestion.live_client.LiveSessionClient.fetch", fetch
    )
    app = AppTest.from_file("dashboard/app.py", default_timeout=120).run()
    next(
        item
        for item in app.checkbox
        if item.label == "Include laps requiring an online download"
    ).check().run()
    selector = next(item for item in app.selectbox if item.label == "VER lap")
    option = next(
        option for option in selector.options if "requires online download" in option
    )
    selector.set_value(int(option.split()[1])).run()
    assert not app.exception
    assert any("No other lap has been substituted" in item.value for item in app.info)
    assert fetch.called
    fetch.reset_mock()
    next(
        item
        for item in app.checkbox
        if item.label == "Include laps requiring an online download"
    ).uncheck().run()
    assert not app.exception
    assert not app.info
    assert len(app.get("plotly_chart")) >= 12
    fetch.assert_not_called()
