from pathlib import Path
import tomllib


def test_cloud_requirements_match_project_and_dashboard_analytics_extras():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    declared = set(project["dependencies"])
    for extra in ("analytics", "dashboard"):
        declared.update(project["optional-dependencies"][extra])
    cloud = {
        line.strip()
        for line in (root / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert cloud == declared
