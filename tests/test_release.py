import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release.py"


@pytest.fixture
def release_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "flaskteroids"\nversion = "0.1.6" # framework\n'
        '\n[tool.example]\nversion = "2.0.0"\n'
    )
    (tmp_path / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "flaskteroids"\nversion = "0.1.6"\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n\n"
        "### Added\n\n- Application configuration.\n\n"
        "## 0.1.6 - 2025-01-01\n\n- Previous changes.\n"
    )
    return tmp_path


@pytest.fixture
def run_release(release_project):
    def run(*args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(release_project), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    return run


@pytest.mark.parametrize(
    ("bump", "expected"),
    [("patch", "0.1.7"), ("minor", "0.2.0"), ("major", "1.0.0")],
)
def test_prepare_updates_version_and_moves_notes(
    release_project, run_release, bump, expected
):
    result = run_release("prepare", bump)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
    project_text = (release_project / "pyproject.toml").read_text()
    project = tomllib.loads(project_text)
    assert project["project"]["version"] == expected
    assert project["tool"]["example"]["version"] == "2.0.0"
    assert "# framework" in project_text
    changelog = (release_project / "CHANGELOG.md").read_text()
    assert f"## Unreleased\n\n## {expected} - {date.today().isoformat()}" in changelog
    assert "## 0.1.6 - 2025-01-01\n\n- Previous changes." in changelog
    notes = run_release("notes")
    assert notes.returncode == 0, notes.stderr
    assert notes.stdout.strip() == "### Added\n\n- Application configuration."


def test_prepare_supports_single_quoted_version(release_project, run_release):
    path = release_project / "pyproject.toml"
    path.write_text(path.read_text().replace('"0.1.6"', "'0.1.6'"))
    result = run_release("prepare", "patch")
    assert result.returncode == 0, result.stderr
    assert "version = '0.1.7' # framework" in path.read_text()


@pytest.mark.parametrize(
    "changelog",
    [
        "# Changelog\n",
        "# Changelog\n\n## Unreleased\n",
        "# Changelog\n\n## Unreleased\n\n<!-- Add notes here. -->\n",
        "## Unreleased\n\n## 0.1.6 - 2025-01-01\n\n- Old notes.\n",
        "## Unreleased\n\n- One.\n\n## Unreleased\n\n- Two.\n",
    ],
)
def test_prepare_rejects_missing_empty_or_duplicate_notes_without_changes(
    release_project, run_release, changelog
):
    path = release_project / "CHANGELOG.md"
    path.write_text(changelog)
    project = (release_project / "pyproject.toml").read_text()
    result = run_release("prepare", "patch")
    assert result.returncode != 0
    assert path.read_text() == changelog
    assert (release_project / "pyproject.toml").read_text() == project


def test_prepare_rejects_existing_release_version(release_project, run_release):
    path = release_project / "CHANGELOG.md"
    changelog = path.read_text() + "\n## 0.1.7 - 2025-01-02\n\n- Already released.\n"
    path.write_text(changelog)
    result = run_release("prepare", "patch")
    assert result.returncode != 0
    assert "already contains version 0.1.7" in result.stderr
    assert path.read_text() == changelog


def test_second_release_moves_only_new_notes(release_project, run_release):
    assert run_release("prepare", "patch").returncode == 0
    path = release_project / "CHANGELOG.md"
    path.write_text(
        path.read_text().replace("## Unreleased", "## Unreleased\n\n- New fix.")
    )
    result = run_release("prepare", "patch")
    assert result.returncode == 0, result.stderr
    assert run_release("notes").stdout.strip() == "- New fix."
    assert "- Application configuration." in path.read_text()


def test_version_reads_project_metadata(run_release):
    result = run_release("version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.1.6"


@pytest.mark.parametrize("version", ["0.2.0rc1", "0.2", "not-a-version"])
def test_prepare_rejects_non_stable_versions(release_project, run_release, version):
    path = release_project / "pyproject.toml"
    path.write_text(path.read_text().replace("0.1.6", version))
    result = run_release("prepare", "patch")
    assert result.returncode != 0
    assert "X.Y.Z" in result.stderr


def test_validate_tag_accepts_matching_release(run_release):
    result = run_release("validate-tag", "v0.1.6")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("tag", ["0.1.6", "v0.1.7", "v0.1.6rc1"])
def test_validate_tag_rejects_mismatched_tag(run_release, tag):
    result = run_release("validate-tag", tag)
    assert result.returncode != 0
    assert "Release tag must be v0.1.6" in result.stderr


def test_validate_tag_rejects_stale_lockfile(run_release):
    assert run_release("prepare", "patch").returncode == 0
    result = run_release("validate-tag", "v0.1.7")
    assert result.returncode != 0
    assert "uv.lock does not match" in result.stderr


def test_validate_tag_rejects_missing_release_notes(release_project, run_release):
    (release_project / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n")
    result = run_release("validate-tag", "v0.1.6")
    assert result.returncode != 0
    assert "changelog heading" in result.stderr


def test_prepare_requires_new_notes_after_release(run_release):
    assert run_release("prepare", "patch").returncode == 0
    result = run_release("prepare", "patch")
    assert result.returncode != 0
    assert "Add user-facing release notes" in result.stderr
