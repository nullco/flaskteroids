import shutil
import sys
from base64 import b64decode
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import pytest
from jinja2 import DictLoader

from flaskteroids.application import Application
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.mailer import MailerPreview
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter
from tests.assertions import HTML

_FIXTURES = Path(__file__).parent / "fixtures"
_PREFIX = "/flaskteroids/mailers"


@pytest.fixture
def preview_app_factory(tmp_path):
    applications = []
    original_modules = set(sys.modules)

    def create(
        *,
        environment="development",
        enabled=None,
        api_only=False,
        paths=None,
        preview_files=None,
    ):
        root = tmp_path / str(len(applications))
        shutil.copytree(_FIXTURES / "previews", root / "test/mailers/previews")
        shutil.copytree(_FIXTURES / "templates", root / "app/views")
        for relative, source in (preview_files or {}).items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)

        class PreviewApplication(Application):
            def configure(self, config):
                config.api_only = api_only
                config.paths.models = "missing.models"
                config.paths.jobs = "missing.jobs"
                config.paths.helpers = "missing.helpers"
                config.paths.controllers = "missing.controllers"
                config.paths.mailers = "missing.mailers"
                config.paths.routes = "tests.mailers.fixtures.routes"
                config.jobs.queue_adapter = TestQueueAdapter
                config.action_mailer.delivery_method = TestDeliveryMethod
                config.action_mailer.perform_deliveries = True
                config.action_mailer.show_previews = enabled
                if paths is not None:
                    config.action_mailer.preview_paths = paths
                config.secret_key_base = "preview-test-key"
                config.i18n.available_locales = ["en", "es"]
                config.enable_reloading = True

            def _configure_database(self):
                self.database_url = "sqlite:///:memory:"

        app = PreviewApplication.initialize(environment=environment, root_path=root)
        app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=True)
        applications.append(app)
        return app

    yield create

    for app in applications:
        app.extensions["flaskteroids.db"].engine.dispose()
    for name in set(sys.modules) - original_modules:
        if name.startswith("_flaskteroids_mail_preview_"):
            sys.modules.pop(name, None)


@pytest.fixture
def preview_app(preview_app_factory):
    return preview_app_factory()


def test_preview_params_are_copied_per_instance():
    params = {"name": "Jane"}
    first = MailerPreview(params)
    second = MailerPreview(params)
    first.params.pop("name")
    assert params == second.params == {"name": "Jane"}
    assert MailerPreview().params == {}


@pytest.mark.parametrize("api_only", [False, True])
def test_development_lists_discovered_scenarios_without_application_layout(
    preview_app_factory, api_only
):
    app = preview_app_factory(api_only=api_only)
    app.jinja_loader = DictLoader({"layout.html": "Application layout"})
    response = app.test_client().get(_PREFIX)
    assert response.status_code == 200
    page = HTML(response.text)
    assert page.has("a", href=f"{_PREFIX}/notice/long_name")
    assert page.has("a", href=f"{_PREFIX}/admin/notice/welcome")
    assert not page.has("a", href=f"{_PREFIX}/notice/_hidden")
    assert not page.has("a", href=f"{_PREFIX}/notice/inherited_scenario")
    assert not page.has("a", href=f"{_PREFIX}/base/inherited_scenario")
    assert "Application layout" not in page.text


@pytest.mark.parametrize("path", ["", "/notice/welcome"])
def test_preview_pages_bundle_the_flaskteroids_logo_and_favicon(preview_app, path):
    response = preview_app.test_client().get(_PREFIX + path)
    assert response.status_code == 200
    page = HTML(response.text)
    assert page.has("a", href=_PREFIX)
    assert page.has("img", alt="Flaskteroids")
    images = {
        "logo-horizontal-dark": next(
            attrs["src"]
            for tag, attrs in page.elements
            if tag == "img" and attrs.get("alt") == "Flaskteroids"
        ),
        "favicon": next(
            attrs["href"]
            for tag, attrs in page.elements
            if tag == "link" and attrs.get("rel") == "icon"
        ),
    }
    for name, url in images.items():
        prefix, encoded = url.split(",", 1)
        assert prefix == "data:image/svg+xml;base64"
        svg = b64decode(encoded)
        assert ElementTree.fromstring(svg).tag == "{http://www.w3.org/2000/svg}svg"
        assert svg == (
            files("flaskteroids")
            .joinpath(f"controllers/templates/brand/{name}.svg")
            .read_bytes()
        )


@pytest.mark.parametrize("environment", ["test", "production"])
def test_non_development_omits_preview_routes_and_imports(
    preview_app_factory, environment
):
    app = preview_app_factory(
        environment=environment,
        preview_files={
            "test/mailers/previews/broken_preview.py": 'raise RuntimeError("Imported preview")'
        },
    )
    assert app.test_client().get(_PREFIX).status_code == 404
    assert not any(
        "mail_previews" in rule.endpoint for rule in app.url_map.iter_rules()
    )


def test_preview_configuration_supports_explicit_enable_and_disable(
    preview_app_factory,
):
    enabled = preview_app_factory(environment="test", enabled=True)
    disabled = preview_app_factory(enabled=False)
    assert enabled.test_client().get(_PREFIX).status_code == 200
    assert disabled.test_client().get(_PREFIX).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/missing/welcome",
        "/notice/missing",
        "/notice/_hidden",
        "/notice/__init__",
        "/notice/inherited_scenario",
        "/notice/params",
        "/notice/welcome?part=xml",
    ],
)
def test_preview_routes_reject_undiscovered_targets(preview_app, path):
    assert preview_app.test_client().get(_PREFIX + path).status_code == 404


def test_nested_preview_group_lists_its_own_scenarios(preview_app):
    client = preview_app.test_client()
    response = client.get(f"{_PREFIX}/admin/notice")
    assert response.status_code == 200
    page = HTML(response.text)
    assert page.has("a", href=f"{_PREFIX}/admin/notice/welcome")
    assert not page.has("a", href=f"{_PREFIX}/admin/notice/long_name")
    response = client.get(f"{_PREFIX}/admin/notice/welcome")
    assert response.status_code == 200
    assert HTML(response.text).has("iframe", title="HTML email preview")


def test_preview_builds_headers_html_and_callbacks_without_delivery(
    preview_app, mocker
):
    mail = preview_app.extensions["flaskteroids.mail"]
    jobs = preview_app.extensions["flaskteroids.jobs"].queue_adapter
    deliver = mocker.spy(mail.delivery_method, "deliver")
    enqueue = mocker.spy(jobs, "enqueue")
    client = preview_app.test_client()
    for _ in range(2):
        response = client.get(
            f"{_PREFIX}/notice/welcome",
            query_string={"greeting": "Bonjour", "name": "Élodie"},
        )
        assert response.status_code == 200
        page = HTML(response.text)
        assert "Bonjour" in page.text
        assert "jane@example.com" in page.text
        iframe = next(attrs for tag, attrs in page.elements if tag == "iframe")
        body = HTML(iframe["srcdoc"])
        assert "Bonjour, Élodie!" in body.text
        assert "Prepared by callback" in body.text
    deliver.assert_not_called()
    enqueue.assert_not_called()


@pytest.mark.parametrize("script_name", ["", "/myapp"])
def test_format_switch_preserves_preview_query_parameters(preview_app, script_name):
    client = preview_app.test_client()
    response = client.get(
        f"{_PREFIX}/notice/welcome",
        query_string=[
            ("greeting", "Hola"),
            ("name", "Ana"),
            ("label", "a"),
            ("label", "b"),
        ],
        environ_overrides={"SCRIPT_NAME": script_name},
    )
    page = HTML(response.text)
    href = next(
        attrs["href"]
        for tag, attrs in page.elements
        if tag == "a" and "part=plain" in attrs.get("href", "")
    )
    assert urlsplit(href).path == f"{script_name}{_PREFIX}/notice/welcome"
    assert parse_qs(urlsplit(href).query) == {
        "greeting": ["Hola"],
        "name": ["Ana"],
        "label": ["a", "b"],
        "part": ["plain"],
    }
    response = client.get(
        href.removeprefix(script_name), environ_overrides={"SCRIPT_NAME": script_name}
    )
    assert response.status_code == 200
    page = HTML(response.text)
    assert page.has("pre")
    assert "Hola, Ana!" in page.text


@pytest.mark.parametrize(
    ("scenario", "tag", "content"),
    [
        ("text_only", "pre", "Plain text for Jane."),
        ("html_only", "iframe", "HTML for Jane."),
    ],
)
def test_single_part_messages_choose_the_available_body(
    preview_app, scenario, tag, content
):
    response = preview_app.test_client().get(f"{_PREFIX}/notice/{scenario}")
    assert response.status_code == 200
    page = HTML(response.text)
    assert page.has(tag)
    if tag == "iframe":
        body = next(
            attrs["srcdoc"] for name, attrs in page.elements if name == "iframe"
        )
        page = HTML(body)
    assert content in page.text


@pytest.mark.parametrize(
    "path",
    ["/notice/empty", "/notice/text_only?part=html", "/notice/html_only?part=plain"],
)
def test_missing_message_parts_have_an_explanatory_view(preview_app, path):
    response = preview_app.test_client().get(_PREFIX + path)
    assert response.status_code == 200
    page = HTML(response.text)
    assert not page.has("iframe")
    assert not page.has("pre")
    assert "This message has no" in page.text


def test_preview_preserves_the_mailer_locale(preview_app):
    response = preview_app.test_client().get(f"{_PREFIX}/notice/localized?locale=es")
    assert response.status_code == 200
    iframe = next(
        attrs for tag, attrs in HTML(response.text).elements if tag == "iframe"
    )
    assert HTML(iframe["srcdoc"]).has("span", lang="es")


def test_html_is_sandboxed_and_message_headers_are_escaped(preview_app):
    greeting = '<img src=x onerror="alert(1)">'
    response = preview_app.test_client().get(
        f"{_PREFIX}/notice/unsafe", query_string={"greeting": greeting}
    )
    assert response.status_code == 200
    page = HTML(response.text)
    assert greeting in page.text
    assert not page.has("img", src="x")
    assert not page.has("script")
    iframe = next(attrs for tag, attrs in page.elements if tag == "iframe")
    assert iframe["sandbox"] == ""
    assert iframe["referrerpolicy"] == "no-referrer"
    assert HTML(iframe["srcdoc"]).has("script")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_plain_text_is_displayed_as_text(preview_app):
    response = preview_app.test_client().get(f"{_PREFIX}/notice/unsafe?part=plain")
    page = HTML(response.text)
    assert page.has("pre")
    assert not page.has("script")
    assert '<script>alert("Text is not HTML")</script>' in page.text


@pytest.mark.parametrize(
    ("scenario", "exception", "message"),
    [
        ("invalid", ProgrammerError, "must return a MessageDelivery"),
        ("broken", ValueError, "Invalid preview data"),
    ],
)
def test_preview_failures_surface_actionable_errors(
    preview_app, scenario, exception, message
):
    with pytest.raises(exception, match=message):
        preview_app.test_client().get(f"{_PREFIX}/notice/{scenario}")


def test_preview_applications_keep_paths_and_rendering_isolated(preview_app_factory):
    first = preview_app_factory()
    second = preview_app_factory(paths=[])
    third = preview_app_factory()
    template = third.project_root / "app/views/preview_notices_mailer/welcome.html"
    template.write_text("<p>Another application's template</p>")
    assert "No previews found" in HTML(second.test_client().get(_PREFIX).text).text
    for app, expected in [
        (first, "Hello, Jane!"),
        (third, "Another application's template"),
    ]:
        response = app.test_client().get(f"{_PREFIX}/notice/welcome")
        iframe = next(
            attrs for tag, attrs in HTML(response.text).elements if tag == "iframe"
        )
        assert expected in HTML(iframe["srcdoc"]).text


def test_template_changes_are_visible_on_refresh(preview_app):
    client = preview_app.test_client()
    client.get(f"{_PREFIX}/notice/welcome")
    template = (
        preview_app.project_root / "app/views/preview_notices_mailer/welcome.html"
    )
    template.write_text("<p>Updated template</p>")
    response = client.get(f"{_PREFIX}/notice/welcome")
    iframe = next(
        attrs for tag, attrs in HTML(response.text).elements if tag == "iframe"
    )
    assert "Updated template" in HTML(iframe["srcdoc"]).text


def test_preview_paths_accept_absolute_paths_and_overlapping_roots(preview_app_factory):
    app = preview_app_factory(
        paths=[
            str(_FIXTURES / "previews"),
            str(_FIXTURES / "previews"),
            str(_FIXTURES / "previews/admin"),
        ]
    )
    response = app.test_client().get(_PREFIX)
    assert response.status_code == 200
    assert HTML(response.text).has("a", href=f"{_PREFIX}/notice/welcome")


def test_missing_preview_directories_show_an_empty_index(preview_app_factory):
    app = preview_app_factory(paths=["missing/previews"])
    response = app.test_client().get(_PREFIX)
    assert response.status_code == 200
    assert "No previews found" in HTML(response.text).text


def test_additional_preview_paths_extend_the_default_directory(preview_app_factory):
    source = (_FIXTURES / "extra_previews/additional_preview.py").read_text()
    app = preview_app_factory(
        paths=["test/mailers/previews", "lib/mailer_previews"],
        preview_files={"lib/mailer_previews/additional_preview.py": source},
    )
    page = HTML(app.test_client().get(_PREFIX).text)
    assert page.has("a", href=f"{_PREFIX}/notice/welcome")
    assert page.has("a", href=f"{_PREFIX}/additional/welcome")


@pytest.mark.parametrize(
    ("source", "exception", "message"),
    [
        (
            "import missing_preview_dependency",
            ModuleNotFoundError,
            "missing_preview_dependency",
        ),
        ("def broken(", SyntaxError, "was never closed"),
    ],
)
def test_enabled_previews_surface_import_failures(
    preview_app_factory, source, exception, message
):
    with pytest.raises(exception, match=message):
        preview_app_factory(
            preview_files={"test/mailers/previews/broken_preview.py": source}
        )


def test_conflicting_preview_names_raise_a_configuration_error(preview_app_factory):
    source = (_FIXTURES / "previews/notice_preview.py").read_text()
    with pytest.raises(ProgrammerError, match="Duplicate mailer preview"):
        preview_app_factory(
            preview_files={"test/mailers/previews/duplicate_preview.py": source}
        )
