import json
import sys
from threading import Thread

from app.models.post import Post
from config.application import Application
from flask import render_template_string
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

app = Application.initialize(environment=sys.argv[1])
production = app.env.production


@app.get("/lexxy-assets")
def editor():
    return render_template_string(
        '{% extends "layouts/application.html" %}{% block body %}'
        '{% call(form) form_with(model=record, url="/posts") %}'
        '{{ form.label("content") }}{{ form.rich_text_area("content") }}'
        "{% endcall %}{% endblock %}",
        record=Post.new(content="<h2>Packaged editor</h2><p>Editable content</p>"),
    )


server = make_server("127.0.0.1", 0, app)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
origin = f"http://127.0.0.1:{server.server_port}"
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors, requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(request.url))
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(origin + "/")
                else route.abort()
            ),
        )
        page.goto(origin + "/lexxy-assets")
        expect(page.get_by_label("Content")).to_be_editable()
        expect(page.get_by_label("Content")).to_contain_text("Packaged editor")
        page.get_by_label("Content").press("End")
        page.get_by_label("Content").press_sequentially(" with keyboard input")
        with page.expect_file_chooser() as chooser:
            page.get_by_role("button", name="Upload files", exact=True).click()
        chooser.value.set_files(
            {"name": "report.txt", "mimeType": "text/plain", "buffer": b"Report"}
        )
        page.wait_for_function(
            "document.querySelector('lexxy-editor').value.includes('sgid=')"
        )
        value = page.locator("lexxy-editor").evaluate(
            "editor => new FormData(editor.form).get(editor.name)"
        )
        assert "with keyboard input" in value
        assert "report.txt" in value
        imports = json.loads(page.locator('script[type="importmap"]').text_content())[
            "imports"
        ]
        for name in ("lexxy", "flaskteroids/rich-text", "@rails/activestorage"):
            url = imports[name]
            assert ("-" in url.rsplit("/", 1)[-1]) == production
            assert origin + url in requests
        styles = page.locator('link[rel="stylesheet"]').evaluate_all(
            "links => links.map(link => link.getAttribute('href'))"
        )
        assert any("lexxy" in url for url in styles)
        assert any("lexxy-content" in url for url in requests)
        assert any("lexxy-editor" in url for url in requests)
        assert any("lexxy-variables" in url for url in requests)
        assert not errors, errors
        assert all(url.startswith(origin + "/") for url in requests), requests
        browser.close()
finally:
    server.shutdown()
    thread.join(timeout=5)
