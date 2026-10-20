import os
import sys
from threading import Thread

from app.models.product import Product
from app.models.session import Session
from app.models.subscriber import Subscriber
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from wsgi import app

from tests.integration.scenarios.routing_support import account

with account(app) as user:
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    product_id = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"),
            )
            page = browser.new_page(java_script_enabled=sys.argv[1] == "enabled")
            # Turbo/remote helpers are outside C1–C4; keep this scenario offline.
            page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
            page.goto(base + "/session/new")
            page.locator('input[name="email_address"]').fill(user.email_address)
            page.locator('input[name="password"]').fill("secret")
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(
                page.get_by_role("heading", name="Products", exact=True)
            ).to_be_visible()

            page.get_by_role("link", name="New product", exact=True).click()
            name = f"Browser product {user.email_address}"
            page.get_by_label("Name", exact=True).fill(name)
            page.get_by_label("Quantity", exact=True).fill("3")
            page.get_by_role("button", name="Submit", exact=True).click()
            expect(
                page.get_by_role("link", name="Edit this product", exact=True)
            ).to_be_visible()
            with app.app_context():
                product_id = Product.find_by(name=name).id
            page.get_by_role("link", name="Edit this product", exact=True).click()
            page.get_by_label("Quantity", exact=True).fill("4")
            page.get_by_role("button", name="Submit", exact=True).click()
            expect(
                page.get_by_role("link", name="Edit this product", exact=True)
            ).to_be_visible()
            with app.app_context():
                assert Product.find(product_id).quantity == 4

            page.get_by_role("link", name="Subscribe to product", exact=True).click()
            page.get_by_label("Email", exact=True).fill("a@b.c")
            page.get_by_role("button", name="Subscribe", exact=True).click()
            expect(page.locator("#errors li")).to_have_count(1)
            expect(page.get_by_label("Email", exact=True)).to_have_value("a@b.c")
            page.get_by_label("Email", exact=True).fill("reader@example.com")
            page.get_by_role("button", name="Subscribe", exact=True).click()
            page.get_by_role("link", name="Edit subscription", exact=True).click()
            expect(page.get_by_label("Email", exact=True)).to_have_value(
                "reader@example.com"
            )
            page.get_by_label("Email", exact=True).fill("changed@example.com")
            page.get_by_role("button", name="Subscribe", exact=True).click()
            expect(
                page.get_by_role("link", name="Edit this product", exact=True)
            ).to_be_visible()
            with app.app_context():
                assert (
                    Subscriber.find_by(product_id=product_id).email
                    == "changed@example.com"
                )

            page.get_by_role("button", name="Destroy this product", exact=True).click()
            expect(
                page.get_by_role("heading", name="Products", exact=True)
            ).to_be_visible()
            with app.app_context():
                assert Product.where(id=product_id).count() == 0
                assert Subscriber.where(product_id=product_id).count() == 0
            product_id = None
            page.get_by_role("button", name="Log out", exact=True).click()
            expect(
                page.get_by_role("button", name="Sign in", exact=True)
            ).to_be_visible()
            with app.app_context():
                assert Session.where(user_id=user.id).count() == 0
            page.goto(base + "/products/new")
            expect(
                page.get_by_role("button", name="Sign in", exact=True)
            ).to_be_visible()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        if product_id is not None:
            with app.app_context():
                Product.find(product_id).destroy()
