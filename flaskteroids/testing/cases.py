from contextlib import ExitStack, contextmanager
from threading import Thread
from typing import ClassVar
from urllib.parse import urlsplit

import pytest
from flask import current_app
from playwright.sync_api import expect
from werkzeug.serving import make_server

from flaskteroids.testing.context import activate_test_context, current_response
from flaskteroids.testing.database import transactional_test
from flaskteroids.testing.fixtures import load_fixtures


class FlaskteroidsTest:
    fixtures: ClassVar[list[str]] = []

    @pytest.fixture(autouse=True)
    def _flaskteroids_test_lifecycle(self, application, request):
        jobs = application.extensions["flaskteroids.jobs"].queue_adapter
        mail = application.extensions["flaskteroids.mail"].delivery_method
        jobs.clear()
        mail.clear()

        with transactional_test(application):
            with application.app_context():
                client = application.test_client()
                with activate_test_context(client):
                    self._fixture_collection = load_fixtures(application, self.fixtures)
                    self._before_test(application, request)
                    try:
                        self.setup()
                        yield
                    finally:
                        try:
                            self.teardown()
                        finally:
                            self._after_test()

    def _before_test(self, application, request):
        pass

    def _after_test(self):
        pass

    def setup(self):
        pass

    def teardown(self):
        pass

    def __getattr__(self, name):
        collection = self.__dict__.get("_fixture_collection")
        if collection is not None and name in collection:
            return getattr(collection, name)
        raise AttributeError(name)

    def fixture(self, fixture_set, label):
        return getattr(self._fixture_collection, fixture_set)(label)

    def assert_response(self, expected):
        response = self._response()
        ranges = {
            "success": range(200, 300),
            "redirect": range(300, 400),
            "error": range(500, 600),
        }
        if expected == "missing":
            assert response.status_code == 404, (
                f"Expected a missing response, got {response.status_code}"
            )
        elif isinstance(expected, str) and expected in ranges:
            assert response.status_code in ranges[expected], (
                f"Expected a {expected} response, got {response.status_code}"
            )
        else:
            assert response.status_code == int(expected)

    def assert_redirected_to(self, location):
        response = self._response()
        assert response.status_code in range(300, 400), (
            f"Expected a redirect, got {response.status_code}"
        )
        actual_url = urlsplit(response.location)
        expected_url = urlsplit(str(location))
        actual = (actual_url.path, actual_url.query)
        expected = (expected_url.path, expected_url.query)
        assert actual == expected, f"Expected redirect to {expected}, got {actual}"

    @contextmanager
    def assert_difference(self, expression, by=1):
        before = expression()
        yield
        after = expression()
        assert after - before == by, (
            f"Expected value to change by {by}, changed by {after - before}"
        )

    @contextmanager
    def assert_changes(self, expression, *, was=None, to=None):
        before = expression()
        if was is not None:
            assert before == was
        yield
        after = expression()
        assert after != before, "Expected value to change, but it did not"
        if to is not None:
            assert after == to

    @contextmanager
    def assert_enqueued_with(self, *, job, args=None, kwargs=None):
        adapter = self._application.extensions["flaskteroids.jobs"].queue_adapter
        start = len(adapter.enqueued_jobs)
        yield
        enqueued = adapter.enqueued_jobs[start:]
        matched = any(
            entry.job_class is job
            and (args is None or entry.args == tuple(args))
            and (kwargs is None or entry.kwargs == kwargs)
            for entry in enqueued
        )
        assert matched, f"Expected {job.__name__} to be enqueued"

    @contextmanager
    def perform_enqueued_jobs(self):
        adapter = self._application.extensions["flaskteroids.jobs"].queue_adapter
        previous = adapter.performing_enqueued_jobs
        adapter.performing_enqueued_jobs = True
        try:
            yield
        finally:
            adapter.performing_enqueued_jobs = previous

    @contextmanager
    def assert_emails(self, count):
        deliveries = self._application.extensions[
            "flaskteroids.mail"
        ].delivery_method.deliveries
        before = len(deliveries)
        yield
        actual = len(deliveries) - before
        assert actual == count, f"Expected {count} emails, got {actual}"

    @property
    def deliveries(self):
        return self._application.extensions[
            "flaskteroids.mail"
        ].delivery_method.deliveries

    @property
    def enqueued_jobs(self):
        return self._application.extensions[
            "flaskteroids.jobs"
        ].queue_adapter.enqueued_jobs

    @property
    def _application(self):
        return current_app._get_current_object()

    def _response(self):
        response = current_response()
        assert response is not None, "No request has been made"
        return response


class ModelTest(FlaskteroidsTest):
    pass


class IntegrationTest(FlaskteroidsTest):
    pass


class JobTest(FlaskteroidsTest):
    pass


class MailerTest(FlaskteroidsTest):
    pass


class SystemTest(IntegrationTest):
    pytestmark = pytest.mark.system

    def _before_test(self, application, request):
        new_context = request.getfixturevalue("system_browser")
        with ExitStack() as resources:
            server = resources.enter_context(make_server("127.0.0.1", 0, application))
            previous_server_name = application.config.get("SERVER_NAME")
            application.config["SERVER_NAME"] = f"127.0.0.1:{server.server_port}"
            resources.callback(
                application.config.__setitem__, "SERVER_NAME", previous_server_name
            )
            server_thread = Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.05},
                daemon=True,
            )
            server_thread.start()
            resources.callback(server_thread.join)
            resources.callback(server.shutdown)
            self._base_url = f"http://127.0.0.1:{server.server_port}"
            context = resources.enter_context(new_context())
            self.page = context.new_page()
            self._system_resources = resources.pop_all()

    def _after_test(self):
        self._system_resources.close()

    def visit(self, location):
        if str(location).startswith(("http://", "https://")):
            url = str(location)
        else:
            url = f"{self._base_url}{location}"
        self.page.goto(url)

    def click_on(self, text):
        self.page.get_by_text(text, exact=True).first.click()

    def fill_in(self, label, *, value):
        self.page.get_by_label(label).fill(str(value))

    def fill_in_rich_text_area(self, label, *, value):
        control = self.page.locator("lexxy-editor").filter(
            has=self.page.get_by_label(label)
        )
        expect(self.page.get_by_label(label)).to_be_editable()
        control.evaluate("(element, html) => { element.value = html }", str(value))

    def attach_file(self, label, path):
        self.page.get_by_label(label).set_input_files(path)

    def assert_text(self, text):
        expect(self.page.get_by_text(text)).to_be_visible()

    def assert_selector(self, selector, *, text=None):
        locator = self.page.locator(selector)
        if text is not None:
            locator = locator.filter(has_text=text)
        expect(locator).to_be_visible()
