import shutil
from pathlib import Path

import pytest

from tests.assertions import assert_pytest_passed


@pytest.fixture(scope="module")
def turbo_application(generated_app_factory):
    root, run = generated_app_factory("turbo_browser")
    run("generate", "scaffold", "Post", "title:string")
    source = Path(__file__).parent / "application/turbo"
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            relative = path.relative_to(source)
            if relative == Path("test/system/browser.py"):
                relative = Path("test/system/turbo_test.py")
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    run("db:prepare")
    return root, run


def test_frames_and_http_streams_in_a_generated_application(turbo_application):
    root, run = turbo_application
    report = root / "turbo-browser.xml"
    run("test:system", "-q", "--junitxml", str(report), "test/system/turbo_test.py")
    assert_pytest_passed(report)
