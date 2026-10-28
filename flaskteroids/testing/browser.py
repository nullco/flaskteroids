import os
from contextlib import ExitStack

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="class")
def system_browser():
    """Reuse Chromium within a system-test class, with isolated test contexts."""
    # Sync Playwright keeps an asyncio loop running on the test thread. Close it
    # between classes so unrelated tests can use their own event loops normally.
    with ExitStack() as resources:
        browser = None

        def new_context():
            nonlocal browser
            if browser is None:
                # A failed launch must stop Playwright immediately, and a later
                # test must be able to retry rather than inherit partial startup.
                with ExitStack() as startup:
                    playwright = startup.enter_context(sync_playwright())
                    started = startup.enter_context(
                        playwright.chromium.launch(
                            headless=True,
                            executable_path=os.environ.get(
                                "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"
                            ),
                        )
                    )
                    resources.enter_context(startup.pop_all())
                browser = started
            return browser.new_context()

        yield new_context
