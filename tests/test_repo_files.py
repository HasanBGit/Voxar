"""CI and release files cannot be run locally, so guard the properties that break them."""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
YAML_FILES = [*WORKFLOWS, ROOT / ".github" / "dependabot.yml", ROOT / ".pre-commit-config.yaml"]


def test_there_are_workflows_to_check() -> None:
    assert len(WORKFLOWS) >= 3


@pytest.mark.parametrize("path", YAML_FILES, ids=lambda p: p.name)
def test_yaml_files_parse(path: Path) -> None:
    assert yaml.safe_load(path.read_text(encoding="utf-8")) is not None


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_full_commit_sha(path: Path) -> None:
    uses = re.findall(
        r"^\s*-?\s*uses:\s*(\S+)", path.read_text(encoding="utf-8"), flags=re.MULTILINE
    )
    unpinned = [u for u in uses if not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", u)]
    assert unpinned == []


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_run_steps_never_interpolate_untrusted_event_data(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    risky = re.compile(r"\$\{\{\s*(github\.event\.|github\.head_ref|inputs\.)")
    offenders = [
        step["run"]
        for job in data["jobs"].values()
        for step in job.get("steps", [])
        if "run" in step and risky.search(step["run"])
    ]
    assert offenders == []
