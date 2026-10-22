import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest


def test_failed_browser_launch_releases_resources_for_subsequent_tests(tmp_path):
    report = tmp_path / "startup.xml"
    scenario = Path(__file__).parent / "scenarios/system_startup.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(scenario), "--junitxml", str(report)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == pytest.ExitCode.TESTS_FAILED, (
        result.stdout + result.stderr
    )
    cases = ElementTree.parse(report).findall(".//testcase")
    assert cases, result.stdout + result.stderr
    for case in cases:
        errors = case.findall("error")
        assert len(errors) == 1, result.stdout + result.stderr
        assert "BrowserStartupError: Browser launch failed" in errors[0].get(
            "message", ""
        ), result.stdout + result.stderr
        assert case.find("failure") is None, result.stdout + result.stderr
