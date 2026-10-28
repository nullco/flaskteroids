import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest


@pytest.fixture
def run_system_scenario(tmp_path):
    def run(name):
        report = tmp_path / f"{name}.xml"
        scenario = Path(__file__).parent / "scenarios" / f"{name}.py"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(scenario), "--junitxml", str(report)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == pytest.ExitCode.TESTS_FAILED, (
            result.stdout + result.stderr
        )
        cases = ElementTree.parse(report).findall(".//testcase")
        assert cases, result.stdout + result.stderr
        return result, cases

    return run


def test_failed_browser_launch_releases_resources_for_subsequent_tests(
    run_system_scenario,
):
    result, cases = run_system_scenario("system_startup")
    for case in cases:
        errors = case.findall("error")
        assert len(errors) == 1, result.stdout + result.stderr
        assert "BrowserStartupError: Browser launch failed" in errors[0].get(
            "message", ""
        ), result.stdout + result.stderr
        assert case.find("failure") is None, result.stdout + result.stderr


@pytest.mark.system
def test_browser_reuse_preserves_isolation_and_recovers_from_lifecycle_errors(
    run_system_scenario,
):
    result, cases = run_system_scenario("system_isolation")
    errors = [error for case in cases for error in case.findall("error")]
    expected = {"BrowserSetupError", "BrowserTeardownError"}
    messages = [error.get("message", "") for error in errors]
    assert all(any(name in message for name in expected) for message in messages), (
        result.stdout + result.stderr
    )
    assert all(any(name in message for message in messages) for name in expected), (
        result.stdout + result.stderr
    )
    assert any(case.find("error") is None for case in cases)
    assert all(case.find("failure") is None for case in cases), (
        result.stdout + result.stderr
    )
