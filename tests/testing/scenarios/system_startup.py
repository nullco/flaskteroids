import asyncio
from threading import enumerate as active_threads

import pytest
from playwright.sync_api import BrowserType

from flaskteroids.testing import SystemTest


class BrowserStartupError(RuntimeError):
    pass


@pytest.fixture
def application(app):
    return app


@pytest.fixture(autouse=True)
def failed_browser_launch(monkeypatch):
    threads = set(active_threads())

    def fail_launch(*args, **kwargs):
        raise BrowserStartupError("Browser launch failed")

    monkeypatch.setattr(BrowserType, "launch", fail_launch)
    yield
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
    assert set(active_threads()) <= threads


class TestBrowserStartup(SystemTest):
    @pytest.mark.parametrize("attempt", [1, 2])
    def test_browser_startup(self, attempt):
        pytest.fail("Browser startup should fail before the test runs")
