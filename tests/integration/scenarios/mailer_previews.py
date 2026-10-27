"""Exercise generated previews through a normally booted development app."""

import os
import sys
from contextlib import ExitStack
from threading import Thread

from config.application import Application
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter
from tests.assertions import HTML


class PreviewApplication(Application):
    def configure(self, config):
        super().configure(config)
        config.mailer.delivery_method = TestDeliveryMethod
        config.jobs.queue_adapter = TestQueueAdapter


def check_browser(app, mailer):
    template = app.project_root / f"app/views/{mailer}/welcome.html"
    template.write_text(
        template.read_text()
        + '<script>parent.document.body.dataset.previewExecuted = "yes"</script>'
    )
    with ExitStack() as resources:
        server = resources.enter_context(make_server("127.0.0.1", 0, app))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        resources.callback(thread.join)
        resources.callback(server.shutdown)
        playwright = resources.enter_context(sync_playwright())
        browser = resources.enter_context(
            playwright.chromium.launch(
                headless=True,
                executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"),
            )
        )
        page = browser.new_page()
        base_url = f"http://127.0.0.1:{server.server_port}"
        page.goto(base_url + "/flaskteroids/mailers")
        header = page.get_by_role("banner")
        logo = header.get_by_role("img", name="Flaskteroids", exact=True)
        for width in (1280, 375, 320):
            page.set_viewport_size({"width": width, "height": 800})
            expect(logo).to_be_visible()
            expect(header.get_by_text("Mailer previews", exact=True)).to_be_visible()
            assert logo.evaluate("(image) => image.complete && image.naturalWidth > 0")
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth"
            )
        page.set_viewport_size({"width": 1280, "height": 800})
        page.get_by_role("link", name="welcome", exact=True).click()
        frame = page.frame_locator('iframe[title="HTML email preview"]')
        expect(frame.locator("body")).to_contain_text("Hi")

        page.goto(f"{base_url}/flaskteroids/mailers/{mailer}/welcome?greeting=Bonjour")
        expect(frame.locator("body")).to_contain_text("Bonjour")
        assert page.locator("body").get_attribute("data-preview-executed") is None
        page.get_by_role("link", name="Plain text", exact=True).click()
        expect(page.locator("pre")).to_contain_text("Bonjour")
        page.get_by_role("link", name="HTML", exact=True).click()
        expect(frame.locator("body")).to_contain_text("Bonjour")
        assert page.locator("body").get_attribute("data-preview-executed") is None
        header.get_by_role("link", name="Flaskteroids", exact=True).click()
        expect(page.get_by_role("link", name="welcome", exact=True)).to_be_visible()


mailer = sys.argv[1]
app = PreviewApplication.initialize(environment="development")
app.config.mailer.perform_deliveries = True
client = app.test_client()
prefix = "/flaskteroids/mailers"
try:
    response = client.get(prefix)
    assert response.status_code == 200
    assert HTML(response.text).has("a", href=f"{prefix}/{mailer}/welcome")

    response = client.get(f"{prefix}/{mailer}/welcome?greeting=Bonjour")
    assert response.status_code == 200
    page = HTML(response.text)
    iframe = next(attrs for tag, attrs in page.elements if tag == "iframe")
    assert "Bonjour" in HTML(iframe["srcdoc"]).text

    href = next(
        attrs["href"]
        for tag, attrs in page.elements
        if tag == "a" and "part=plain" in attrs.get("href", "")
    )
    response = client.get(href)
    assert response.status_code == 200
    assert "Bonjour" in HTML(response.text).text
    assert app.extensions["flaskteroids.mail"].delivery_method.deliveries == []
    assert app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs == []
    if sys.argv[2:] == ["browser"]:
        check_browser(app, mailer)
finally:
    app.extensions["flaskteroids.db"].engine.dispose()
