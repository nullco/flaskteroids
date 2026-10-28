import asyncio

import pytest
from flask import current_app, url_for

from flaskteroids.testing import SystemTest


class BrowserSetupError(RuntimeError):
    pass


class BrowserTeardownError(RuntimeError):
    pass


@pytest.fixture(scope="session")
def observations():
    state = {"browsers": {}, "pages": []}
    yield state
    assert all(page.is_closed() for page in state["pages"])
    assert all(not browser.is_connected() for browser in state["browsers"].values())


@pytest.fixture
def failure():
    return None


@pytest.fixture
def application(app, observations, failure, request):
    app.config["BROWSER_CLASS"] = request.cls
    app.config["OBSERVATIONS"] = observations
    app.config["BROWSER_FAILURE"] = failure
    original_server_name = app.config.get("SERVER_NAME")
    app.add_url_rule(
        "/isolation",
        endpoint="isolation",
        view_func=lambda: (
            f'<p>Ready</p><a href="{url_for("isolation", _external=True)}">Reload</a>'
        ),
    )
    yield app
    assert app.config.get("SERVER_NAME") == original_server_name


def observe_page(page):
    state = current_app.config["OBSERVATIONS"]
    browser = page.context.browser
    test_class = current_app.config["BROWSER_CLASS"]
    assert browser is state["browsers"].setdefault(test_class, browser)
    assert len(browser.contexts) == 1
    assert page.context.cookies() == []
    for previous in state["pages"]:
        assert previous.is_closed()
        assert page.context is not previous.context
    state["pages"].append(page)
    page.context.add_cookies(
        [
            {
                "name": "previous-test",
                "value": "secret",
                "domain": "127.0.0.1",
                "path": "/",
            }
        ]
    )


class TestBrowserIsolation(SystemTest):
    @pytest.mark.parametrize("attempt", [1, 2])
    def test_browser_is_reused_with_an_isolated_context(self, attempt):
        observe_page(self.page)
        self.visit("/isolation")
        self.assert_text("Ready")
        assert (
            self.page.get_by_role("link", name="Reload").get_attribute("href")
            == self.page.url
        )


class TestBrowserRecovery(SystemTest):
    def setup(self):
        observe_page(self.page)
        if current_app.config["BROWSER_FAILURE"] == "setup":
            raise BrowserSetupError("Application test setup failed")

    def teardown(self):
        if current_app.config["BROWSER_FAILURE"] == "teardown":
            raise BrowserTeardownError("Application test teardown failed")

    @pytest.mark.parametrize("failure", ["setup", "teardown", "none"])
    def test_browser_recovers(self, failure):
        self.visit("/isolation")
        self.assert_text("Ready")


async def ready():
    return "ready"


def test_plain_test_can_run_its_own_event_loop():
    assert asyncio.run(ready()) == "ready"
