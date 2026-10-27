import pytest
from flask import render_template, render_template_string
from jinja2 import DictLoader, TemplateNotFound, UndefinedError

from flaskteroids.concern import Concern
from flaskteroids.controller import Controller, helper, helper_method, init
from flaskteroids.exceptions import ProgrammerError
from tests.assertions import HTML
from tests.views.fixtures.controllers.admin.reports_controller import ReportsController
from tests.views.fixtures.controllers.other_controller import OtherController
from tests.views.fixtures.controllers.posts_controller import PostsController
from tests.views.fixtures.helpers.chosen_helper import ChosenHelper
from tests.views.fixtures.mailers.letters_mailer import PersonalLettersMailer
from tests.views.fixtures.mailers.notes_mailer import NotesMailer, PlainMailer


@pytest.mark.parametrize("path", ["/", "/special"])
def test_automatic_helpers_share_controller_and_framework_helpers(
    view_app_factory, path
):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {
            "probe.html": (
                "{{ post_link('<Reader>') }}|{{ price(1250) }}|"
                "{{ viewer_label() }}|{{ caption() }}|"
                "{{ _label is defined }}|{{ _unregistered is defined }}"
            )
        }
    )

    response = app.test_client().get(
        path, headers={"X-Viewer": "member", "X-Title": "<Posts>"}
    )

    assert response.status_code == 200
    html = HTML(response.text)
    assert html.has("a", href="/")
    assert html.text == "Flaskteroids: <Reader>|$12.50|member|<Posts>|False|False"
    assert "&lt;Reader&gt;" in response.text
    assert "&lt;Posts&gt;" in response.text


def test_controller_templates_and_helpers_share_instance_params(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {"probe.html": "{{ input_value() }}|{{ params.value }}"}
    )
    client = app.test_client()
    assert client.get("/?value=First").text == "First|First"
    assert client.get("/?value=Second").text == "Second|Second"


def test_helper_state_is_shared_by_layout_and_partial_but_resets_per_render(
    view_app_factory,
):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {
            "layout.html": "{{ next_number() }}|{% block body %}{% endblock %}",
            "probe.html": (
                "{% extends 'layout.html' %}{% block body %}"
                "{{ render('partial.html') }}|{{ next_number() }}{% endblock %}"
            ),
            "partial.html": "{{ next_number() }}",
        }
    )
    client = app.test_client()

    assert client.get("/").text == "1|2|3"
    assert client.get("/").text == "1|2|3"
    with app.app_context():
        assert render_template("probe.html") == "1|2|3"
        assert render_template("probe.html") == "1|2|3"


def test_partial_failures_restore_the_render_scope(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {"probe.html": "{{ next_number() }}{{ render('missing.html') }}"}
    )

    @app.get("/recover")
    def recover():
        PostsController()
        with pytest.raises(TemplateNotFound):
            render_template("probe.html")
        return render_template_string("{{ next_number() }}")

    assert app.test_client().get("/recover").text == "1"


def test_conventional_selection_inherits_helpers_and_excludes_other_controllers(
    view_app_factory,
):
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader(
        {
            "probe.html": (
                "{{ site_name() }}|{{ post_link is defined }}|"
                "{{ unrelated is defined }}|{{ chosen is defined }}|"
                "{{ price is defined }}|{{ choice() }}"
            )
        }
    )
    client = app.test_client()

    assert client.get("/").text == "Flaskteroids|True|False|False|False|posts"
    assert client.get("/special").text == "Flaskteroids|True|False|True|True|chosen"

    with app.app_context():
        assert render_template("probe.html") == (
            "Flaskteroids|False|False|False|False|application"
        )


def test_nested_conventions_preserve_controller_inheritance(view_app_factory):
    app = view_app_factory(include_all=False)
    init(ReportsController)
    app.jinja_loader = DictLoader(
        {
            "probe.html": "{{ site_name() }}|{{ report_name() }}|{{ post_link is defined }}"
        }
    )
    app.add_url_rule("/reports", view_func=lambda: ReportsController().show())

    assert app.test_client().get("/reports").text == "Flaskteroids|Reports|True"


def test_helper_selection_and_controller_delegates_remain_isolated(view_app_factory):
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader(
        {
            "probe.html": (
                "{{ viewer() }}|{{ post_link is defined }}|{{ unrelated is defined }}"
            )
        }
    )

    @app.get("/other")
    def other():
        OtherController()
        return render_template("probe.html")

    client = app.test_client()
    assert client.get("/", headers={"X-Viewer": "first"}).text == "first|True|False"
    assert (
        client.get("/other", headers={"X-Viewer": "second"}).text == "second|False|True"
    )
    with app.app_context():
        assert render_template_string("{{ viewer is defined }}") == "False"


def test_helper_classes_compose_with_super_and_preserve_module_deduplication(
    view_app_factory,
):
    class ExtraHelper:
        def choice(self):
            return "extra:" + super().choice()

    class CustomController(PostsController):
        helper(ExtraHelper, ChosenHelper)

    init(CustomController)
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader({"probe.html": "{{ choice() }}|{{ chosen() }}"})
    app.add_url_rule("/custom", view_func=lambda: CustomController().show())

    class ReversedController(PostsController):
        helper(ChosenHelper, ExtraHelper, ChosenHelper)

    init(ReversedController)
    app.add_url_rule(
        "/reversed", endpoint="reversed", view_func=lambda: ReversedController().show()
    )
    # Later includes win, and an already-included mixin is not moved.
    assert app.test_client().get("/custom").text == "chosen|chosen"
    assert app.test_client().get("/reversed").text == "extra:chosen|chosen"


def test_child_helper_inclusions_can_override_inherited_controller_helpers(
    view_app_factory,
):
    class ParentController(Controller):
        helper_method("_choice", name="choice")
        helper(ChosenHelper)

        def show(self):
            return render_template("probe.html")

        def _choice(self):
            return "controller"

    class ChildHelper:
        def choice(self):
            return "child"

    class ChildController(ParentController):
        helper(ChildHelper)

    init(ParentController)
    init(ChildController)
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader({"probe.html": "{{ choice() }}"})
    app.add_url_rule(
        "/parent", endpoint="parent", view_func=lambda: ParentController().show()
    )
    app.add_url_rule(
        "/child", endpoint="child", view_func=lambda: ChildController().show()
    )
    client = app.test_client()

    assert client.get("/parent").text == "controller"
    assert client.get("/child").text == "child"


def test_automatic_loading_uses_deterministic_name_order(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader({"probe.html": "{{ choice() }}"})

    assert app.test_client().get("/").text == "posts"


def test_application_helpers_can_override_framework_helpers(view_app_factory):
    class LinksHelper:
        def link_to(self, name, path):
            return f"{name} at {path}"

    class CustomController(PostsController):
        helper(LinksHelper)

    init(CustomController)
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader({"probe.html": "{{ post_link('<Reader>') }}"})
    app.add_url_rule("/custom", view_func=lambda: CustomController().show())

    assert app.test_client().get("/custom").text == "Flaskteroids: &lt;Reader&gt; at /"


@pytest.mark.parametrize("delivery", ["deliver_now", "deliver_later"])
def test_mailers_include_explicit_helpers_without_request_controller_leakage(
    view_app_factory, delivery
):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {
            "probe.html": "{{ viewer() }}",
            "notes_mailer/welcome.html": (
                "{{ greeting('Reader') }}|{{ price(1500) }}|{{ caption() }}|"
                "{{ viewer is defined }}|{{ post_link is defined }}"
            ),
        }
    )
    with app.test_request_context("/"):
        PostsController()
        message = NotesMailer().welcome()
        getattr(message, delivery)()
        if delivery == "deliver_later":
            app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        delivered = app.extensions["flaskteroids.mail"].delivery_method.deliveries[-1]
        assert delivered.get_content_type() == "multipart/alternative"
        assert delivered.get_body(preferencelist=("html",)).get_content().strip() == (
            "Flaskteroids: Reader|$15.00|Newsletter|False|False"
        )
        assert render_template("probe.html") == "guest"


@pytest.mark.parametrize("delivery", ["deliver_now", "deliver_later"])
@pytest.mark.parametrize("in_request", [False, True])
def test_mailer_helper_methods_use_inherited_mailer_state_across_message_parts(
    view_app_factory, delivery, in_request
):
    app = view_app_factory()
    template = (
        "{{ letter_greeting() }}|{{ delivery_number() }}|"
        "{{ viewer is defined }}|{{ _next_number is defined }}"
    )
    app.jinja_loader = DictLoader(
        {
            "personal_letters_mailer/welcome.txt": template,
            "personal_letters_mailer/welcome.html": template,
        }
    )
    context = app.test_request_context("/") if in_request else app.app_context()
    with context:
        if in_request:
            PostsController()
        message = PersonalLettersMailer("Reader <X>").welcome()
        getattr(message, delivery)()
        if delivery == "deliver_later":
            app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        delivered = app.extensions["flaskteroids.mail"].delivery_method.deliveries[-1]
        plain = delivered.get_body(preferencelist=("plain",)).get_content().strip()
        html = delivered.get_body(preferencelist=("html",)).get_content().strip()
        assert plain == "Dear Reader <X>! from Notes|1|False|False"
        assert HTML(html).text == "Dear Reader <X>! from Notes|2|False|False"
        assert "&lt;X&gt;" in html
        if in_request:
            assert render_template_string("{{ viewer() }}") == "guest"
        else:
            assert render_template_string("{{ delivery_number is defined }}") == "False"


def test_queued_mailer_helpers_keep_message_state_separate(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {"personal_letters_mailer/welcome.html": "{{ letter_greeting() }}"}
    )
    with app.app_context():
        for recipient in ("First", "Second"):
            PersonalLettersMailer(recipient).welcome().deliver_later()
        app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        deliveries = app.extensions["flaskteroids.mail"].delivery_method.deliveries
        assert [
            mail.get_body(preferencelist=("html",)).get_content().strip()
            for mail in deliveries
        ] == ["Dear First! from Notes", "Dear Second! from Notes"]


def test_mailer_failures_restore_controller_helper_scope(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {"notes_mailer/welcome.html": "{{ missing_helper() }}"}
    )
    with app.test_request_context("/"):
        PostsController()
        with pytest.raises(UndefinedError):
            NotesMailer().welcome().deliver_now()
        assert render_template_string("{{ viewer() }}") == "guest"


def test_mailers_and_standalone_rendering_have_explicit_helper_boundaries(
    view_app_factory,
):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {
            "plain_mailer/welcome.html": "{{ site_name is defined }}|{{ viewer is defined }}"
        }
    )
    with app.app_context():
        PlainMailer().welcome().deliver_now()
        delivered = app.extensions["flaskteroids.mail"].delivery_method.deliveries[-1]
        assert delivered.get_body(preferencelist=("html",)).get_content().strip() == (
            "False|False"
        )
        assert render_template_string("{{ site_name() }}|{{ viewer is defined }}") == (
            "Flaskteroids|False"
        )


def test_helpers_are_isolated_between_applications(view_app_factory):
    first = view_app_factory()
    second = view_app_factory(include_all=False)
    template = "{{ post_link is defined }}|{{ viewer is defined }}|{{ next_number() }}"

    with first.app_context():
        assert render_template_string(template) == "True|False|1"
        with second.app_context():
            assert render_template_string(template) == "False|False|1"
        assert render_template_string(template) == "True|False|1"


@pytest.mark.parametrize(
    "spec, expression, expected",
    [
        ("chosen", "chosen()", "chosen"),
        ("Chosen", "chosen()", "chosen"),
        ("ChosenHelper", "chosen()", "chosen"),
        ("admin/money", "price(1250)", "$12.50"),
        ("admin.money", "price(1250)", "$12.50"),
        ("admin/MoneyHelper", "price(1250)", "$12.50"),
        ("all", "unrelated()", "other"),
    ],
)
def test_explicit_helper_names_resolve_conventions(
    view_app_factory, spec, expression, expected
):
    class CustomController(PostsController):
        helper(spec)

    init(CustomController)
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader({"probe.html": "{{ " + expression + " }}"})
    app.add_url_rule("/custom", view_func=lambda: CustomController().show())

    assert app.test_client().get("/custom").text == expected


def test_concern_helper_methods_override_same_owner_helper_modules(view_app_factory):
    class Choice(Concern):
        helper_method("_choice", name="choice")

        def _choice(self):
            return "controller"

    class CustomController(Controller, Choice):
        helper(ChosenHelper)

        def show(self):
            return render_template("probe.html")

    init(CustomController)
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader({"probe.html": "{{ choice() }}"})
    app.add_url_rule("/custom", view_func=lambda: CustomController().show())

    assert app.test_client().get("/custom").text == "controller"


def test_explicit_missing_helpers_raise_diagnostic_errors(view_app_factory):
    class CustomController(PostsController):
        helper("missing_helper")

    init(CustomController)
    app = view_app_factory()
    app.add_url_rule("/custom", view_func=lambda: CustomController().show())

    with pytest.raises(ProgrammerError, match="Helper not found for <missing_helper>"):
        app.test_client().get("/custom")


def test_helpers_extension_initialization_preserves_application_isolation(
    view_app_factory,
):
    first = view_app_factory()
    second = view_app_factory()
    extension = first.extensions["flaskteroids.helpers"]
    extension.init_app(first)

    with pytest.raises(ProgrammerError, match="cannot be shared"):
        extension.init_app(second)
    with first.app_context():
        assert render_template_string("{{ next_number() }}") == "1"


@pytest.mark.parametrize("values", [(), (None,), (123,), ("",)])
def test_explicit_helper_declarations_reject_invalid_inputs(values):
    with pytest.raises(ProgrammerError, match="helper classes"):

        class InvalidController(Controller):
            helper(*values)
