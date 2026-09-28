"""Reproduce the supplied Cloud package versions in an isolated Python environment.

Run with the isolated environment's Python, which must already have uv installed.
Never installs into the app's existing environment unless explicitly run there.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cloud-log", type=Path, required=True)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Only raw FastF1 loading; no SciPy interpolation or UI probes",
    )
    args = parser.parse_args()
    folder = ROOT / "logs" / "cloud-repro" / str(time.time_ns())
    folder.mkdir(parents=True)
    # Read only the first installation block; later updates contain +/- removals.
    block = args.cloud_log.read_text(encoding="utf-8").split("Checking if Streamlit")[0]
    packages = dict(re.findall(r"^ \+ ([\w-]+)==([^\s]+)$", block, re.MULTILINE))
    if not packages or "fastf1" not in packages:
        raise ValueError("The log has no recognisable Cloud installation block")
    # Cloud's own compatibility step replaced 25.0.1 with 24.0.0.
    packages["pyarrow"] = "24.0.0"
    constraints = folder / "cloud-constraints.txt"
    constraints.write_text(
        "\n".join(f"{k}=={v}" for k, v in sorted(packages.items())) + "\n"
    )
    results = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "commands": [],
    }
    interpreter = os.path.relpath(sys.executable, ROOT)

    def run(label: str, arguments: list[str]) -> None:
        command = [interpreter, *arguments]
        with (folder / f"{label}.log").open("w", encoding="utf-8") as output:
            result = subprocess.run(
                command,
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=900,
                check=False,
            )
        results["commands"].append(
            {"label": label, "command": command, "returncode": result.returncode}
        )
        (folder / "results.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(label, result.returncode, folder / f"{label}.log", flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect its complete log")

    if args.install:
        run(
            "install",
            [
                "-m",
                "uv",
                "pip",
                "install",
                "--cache-dir",
                "logs/cloud-repro/uv-cache",
                "--python",
                interpreter,
                "-r",
                "requirements.txt",
                "-c",
                str(constraints.relative_to(ROOT)),
            ],
        )
        run(
            "check",
            [
                "-m",
                "uv",
                "pip",
                "check",
                "--cache-dir",
                "logs/cloud-repro/uv-cache",
                "--python",
                interpreter,
            ],
        )
        run(
            "freeze",
            [
                "-m",
                "uv",
                "pip",
                "freeze",
                "--cache-dir",
                "logs/cloud-repro/uv-cache",
                "--python",
                interpreter,
            ],
        )
    if args.probe:
        for year, event in (
            (2022, "Italian Grand Prix"),
            (2023, "Italian Grand Prix"),
            (2023, "Bahrain Grand Prix"),
            (2024, "Italian Grand Prix"),
        ):
            run(
                f"cold_{year}_{event.split()[0]}",
                [
                    "scripts/diagnose_sessions.py",
                    "--mode",
                    "standalone",
                    "--year",
                    str(year),
                    "--event",
                    event,
                    "--fresh-cache",
                    *(["--raw-only"] if args.raw_only else []),
                ],
            )
        if args.raw_only:
            return
        run(
            "fresh_app_2023",
            ["scripts/diagnose_sessions.py", "--mode", "fresh", "--year", "2023"],
        )
        run("transition", ["scripts/diagnose_sessions.py", "--mode", "transition"])


if __name__ == "__main__":
    main()
