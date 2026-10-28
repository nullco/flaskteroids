import json
import os
import shutil
import sys
from threading import Thread

from flask import render_template
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from wsgi import app

production = sys.argv[1] == "production"
app.add_url_rule(
    "/asset-test/", view_func=lambda: render_template("layouts/application.html")
)
server = make_server("127.0.0.1", 0, app)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
            or shutil.which("google-chrome"),
        )
        page = browser.new_page()
        requests = []
        page.on("request", lambda request: requests.append(request.url))
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith("http://127.0.0.1:")
                else route.abort()
            ),
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/asset-test/")
        page.wait_for_function("!!window.Turbo && !!customElements.get('turbo-frame')")
        importmap = json.loads(page.locator('script[type="importmap"]').text_content())
        turbo_src = importmap["imports"]["@hotwired/turbo"]
        assert ("turbo-" in turbo_src) == production
        page.wait_for_function("window.importmapResult === 42")
        assert not any("/optional" in url for url in requests)
        assert page.evaluate("window.loadOptional()") == 43
        assert any("/optional" in url for url in requests)
        href = page.locator('link[rel="stylesheet"]').get_attribute("href")
        assert href.startswith("/assets/stylesheets/application")
        assert ("application-" in href) == production
        assert (
            page.locator("body").evaluate("(body) => getComputedStyle(body).color")
            == "rgb(255, 0, 0)"
        )
        background = page.locator("body").evaluate(
            "(body) => getComputedStyle(body).backgroundImage"
        )
        assert ("logo-" in background) == production
        assert (
            page.evaluate("""async () => {
                const image = new Image();
                image.src = getComputedStyle(document.body).backgroundImage.slice(5, -2);
                await image.decode();
                return image.naturalWidth;
            }""")
            == 1
        )
        browser.close()
finally:
    server.shutdown()
    thread.join(timeout=5)
