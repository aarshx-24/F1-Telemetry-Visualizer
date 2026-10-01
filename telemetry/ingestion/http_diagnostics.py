"""Opt-in, server-only diagnostics. Run in a child process, never in the app loader.

Uses the installed FastF1 HTTP client and headers, with bounded timeouts. Only
public timing endpoints are probed. No authentication, TLS or rate-limit changes.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

PREFIX = "F1_HTTP_DIAGNOSTIC "
ORIGINS = ("https://livetiming.formula1.com", "https://livetiming-mirror.fastf1.dev")
CHANNELS = (
    "session_info",
    "driver_list",
    "session_status",
    "track_status",
    "timing_data",
    "timing_app_data",
    "weather_data",
    "car_data",
    "position",
)
ERROR_PHRASES = re.compile(
    r"access denied|accessdenied|forbidden|not found|blobnotfound|resourcenotfound|"
    r"too many requests|service unavailable|bad gateway|request blocked|authenticationfailed",
    re.IGNORECASE,
)


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    # Diagnostic URLs have no queries. Redirects may contain credentials/signatures.
    return urlunsplit(
        (
            parts.scheme,
            parts.hostname or "",
            parts.path,
            "REDACTED" if parts.query else "",
            "",
        )
    )


def response_metadata(response, requested_url: str) -> dict:
    body = response.content
    # Do not log arbitrary HTML, JSON, IP addresses, tokens, headers or cookies.
    phrases = sorted(
        {
            match.group(0).lower()
            for match in ERROR_PHRASES.finditer(
                body[:2048].decode("utf-8", errors="replace")
            )
        }
    )
    return {
        "requested_url": safe_url(requested_url),
        "final_url": safe_url(response.url),
        "status": response.status_code,
        "redirects": [
            {"status": item.status_code, "url": safe_url(item.url)}
            for item in response.history
        ],
        "content_type": re.sub(r"[\r\n]", "", response.headers.get("Content-Type", ""))[
            :120
        ],
        "response_bytes": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "from_cache": bool(getattr(response, "from_cache", False)),
        "expired": bool(getattr(response, "is_expired", False)),
        "sanitized_error_excerpt": "; ".join(phrases)[:160],
    }


def index_matches(payload: dict, expected_path: str) -> list[dict]:
    matches = []
    for meeting in payload.get("Meetings", []):
        for session in meeting.get("Sessions", []):
            path = session.get("Path", "")
            normal = (
                path if path.startswith("/static/") else "/static/" + path.lstrip("/")
            )
            if normal == expected_path:
                matches.append(
                    {
                        "path": normal,
                        "session_name": session.get("Name"),
                        "meeting_name": meeting.get("Name"),
                    }
                )
    return matches


def snapshot_http_cache(source: Path, destination: Path) -> bool:
    """SQLite's read-only backup API preserves the live database and WAL state."""
    database = source / "fastf1_http_cache.sqlite"
    if not database.is_file():
        return False
    destination.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    def progress(*_):
        if time.monotonic() - started > 15:
            raise TimeoutError("Cache snapshot deadline exceeded")

    with (
        sqlite3.connect(
            database.resolve().as_uri() + "?mode=ro", uri=True, timeout=2
        ) as src,
        sqlite3.connect(destination / database.name) as dst,
    ):
        src.backup(dst, pages=256, progress=progress)
    return True


def run_probe(
    root: Path, output_dir: Path, years: tuple[int, ...], run_id: str
) -> None:
    # Native library logs can include raw responses or environment URLs. This
    # process emits only the deliberately bounded records below.
    logging.disable(logging.CRITICAL)
    import fastf1
    from fastf1 import _api as api

    output_dir.mkdir(parents=True, exist_ok=True)
    logfile = output_dir / "http.jsonl"

    def emit(event: str, **fields) -> None:
        record = {
            "event": event,
            "run_id": run_id,
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **fields,
        }
        line = json.dumps(record, sort_keys=True)
        with logfile.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(PREFIX + line, flush=True)

    if (api.base_url, api.base_url_mirror) != ORIGINS:
        emit(
            "unsupported_client",
            reason="Installed FastF1 origins changed; review before probing",
        )
        return
    emit(
        "start",
        years=years,
        fastf1=fastf1.__version__,
        requests=importlib.metadata.version("requests"),
        requests_cache=importlib.metadata.version("requests-cache"),
        fetch_logic_sha256=hashlib.sha256(
            inspect.getsource(api.fetch_page).encode()
        ).hexdigest(),
        tls_verification=True,
        timeout_seconds=[5, 25],
        mirror_rule="FastF1 fetch_page uses mirror for primary status >=400; direct mirror probes are labelled",
    )
    snapshot = output_dir / "snapshot"
    snapshot.mkdir(exist_ok=True)
    try:
        copied = snapshot_http_cache(root / "data/cache", snapshot)
        emit("cache_snapshot", copied=copied)
    except Exception as exc:  # noqa: BLE001 - diagnostic capture must be best-effort.
        emit("cache_snapshot_failed", exception_type=type(exc).__name__)
        copied = False

    blocked_hosts = set()

    def get(url: str, phase: str, role: str, attempt: int = 1):
        host = urlsplit(url).hostname
        if host in blocked_hosts:
            emit(
                "skipped",
                requested_url=safe_url(url),
                reason="Host returned 429; no further requests this run",
            )
            return None
        started = time.monotonic()
        try:
            response = fastf1.Cache.requests_get(
                url, headers=api.headers, timeout=(5, 25)
            )
            emit(
                "http",
                phase=phase,
                role=role,
                attempt=attempt,
                elapsed_seconds=round(time.monotonic() - started, 3),
                **response_metadata(response, url),
            )
            if response.status_code == 429:
                blocked_hosts.add(host)
            return response
        except Exception as exc:  # noqa: BLE001 - transport failures are probe output.
            # Exception messages can contain proxy credentials; type is safe.
            emit(
                "transport_error",
                phase=phase,
                requested_url=safe_url(url),
                role=role,
                exception_type=type(exc).__name__,
            )
            return None

    for phase in ("snapshot", "fresh") if copied else ("fresh",):
        cache = output_dir / phase
        cache.mkdir(exist_ok=True)
        fastf1.Cache.enable_cache(str(cache))
        settings = fastf1.Cache._requests_session_cached.settings
        emit(
            "cache_policy",
            phase=phase,
            allowable_codes=list(settings.allowable_codes),
            stale_if_error=settings.stale_if_error,
            cache_control=settings.cache_control,
        )
        for year in years:
            try:
                session = fastf1.get_session(year, "Italian Grand Prix", "Q")
                path = session.api_path
                if (
                    session.event.EventName != "Italian Grand Prix"
                    or not path.startswith(f"/static/{year}/")
                ):
                    raise ValueError("Unexpected resolved session")
            except Exception as exc:  # noqa: BLE001 - resolution failures are probe output.
                emit(
                    "resolution_failed",
                    year=year,
                    phase=phase,
                    exception_type=type(exc).__name__,
                )
                continue
            emit(
                "resolved",
                year=year,
                phase=phase,
                path=path,
                round=int(session.event.RoundNumber),
            )
            for origin in ORIGINS:
                index = get(
                    f"{origin}/static/{year}/Index.json", phase, "upstream_year_index"
                )
                if index is not None and index.status_code == 200:
                    try:
                        matches = index_matches(index.json(), path)
                        emit(
                            "index_verification",
                            year=year,
                            phase=phase,
                            origin=origin,
                            matched=bool(matches),
                            matches=matches,
                        )
                    except (ValueError, TypeError, AttributeError):
                        emit("index_unparseable", year=year, phase=phase, origin=origin)
            for channel in CHANNELS:
                for origin in ORIGINS:
                    url = origin + path + api.pages[channel]
                    role = (
                        "primary"
                        if origin == ORIGINS[0]
                        else "direct_official_mirror_probe"
                    )
                    first = get(url, phase, role)
                    # Recheck errors and one representative success to establish
                    # whether the installed cache stores/serves those responses.
                    if first is not None and (
                        first.status_code >= 400 or channel == "session_info"
                    ):
                        second = get(url, phase, role, attempt=2)
                        if second is not None:
                            emit(
                                "cache_recheck",
                                phase=phase,
                                requested_url=url,
                                first_status=first.status_code,
                                second_status=second.status_code,
                                second_from_cache=bool(
                                    getattr(second, "from_cache", False)
                                ),
                            )
            emit("session_probe_complete", year=year, phase=phase)
    emit("complete")
