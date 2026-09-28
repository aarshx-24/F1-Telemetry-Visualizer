import hashlib
import logging
from types import SimpleNamespace

from utils.runtime_diagnostics import log_runtime


def test_runtime_fingerprint_detects_stale_imports(tmp_path, monkeypatch, caplog):
    app = tmp_path / "dashboard/app.py"
    loader = tmp_path / "telemetry/ingestion/fastf1_session_loader.py"
    app.parent.mkdir(parents=True)
    loader.parent.mkdir(parents=True)
    app.write_text("# app")
    loader.write_text("# original loader")
    loaded_hash = hashlib.sha256(loader.read_bytes()).hexdigest()
    monkeypatch.setattr(
        "utils.runtime_diagnostics.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="test-revision"),
    )
    with caplog.at_level(logging.INFO):
        first = log_runtime(tmp_path, loaded_hash)
        assert "STALE_LOADER" not in caplog.text
        loader.write_text("# new loader on disk, old module still imported")
        second = log_runtime(tmp_path, loaded_hash)
    assert first != second
    assert "STALE_LOADER" in caplog.text
    assert "test-revision" in caplog.text
