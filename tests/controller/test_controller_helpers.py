import pytest
from flask import render_template, request
from jinja2 import DictLoader

from flaskteroids.actions import get_actions
from flaskteroids.concern import Concern
from flaskteroids.controller import ActionController, helper_method, init
from flaskteroids.exceptions import ProgrammerError


@pytest.fixture
def helper_app(app, mocker, render_template):
    mocker.stop(render_template)
    app.jinja_loader = DictLoader(
        {
            "layout.html": "{{ label('layout') }}{% block body %}{% endblock %}",
            "helpers/show.html": (
                "{% extends 'layout.html' %}{% block body %}"
                "{{ label(value) }}{{ render('helpers/_label.html') }}"
                "{% endblock %}"
            ),
            "helpers/_label.html": "{{ label('partial') }}",
            "unrelated.html": "{{ label is defined }}|{{ secret is defined }}",
        }
    )
    return app


@pytest.fixture
def helpers_controller():
    class Labels(Concern):
        helper_method("_label", name="label")

        def _label(self, value):
            return f"{self.prefix}:{value}"

    class HelpersController(ActionController, Labels):
        def show(self):
            self.prefix = request.headers.get("X-Prefix", "default")
            self.value = "<example>"
            if request.args.get("explicit"):
                return self.render("show", status=422)

        def _secret(self):
            return "private"

    return init(HelpersController)


@pytest.mark.parametrize("explicit", [False, True])
def test_helpers_render_in_views_layouts_and_partials(
    helper_app, helpers_controller, explicit
):
    helper_app.add_url_rule("/helpers", view_func=lambda: helpers_controller().show())
    client = helper_app.test_client()

    for prefix in ("first", "second"):
        response = client.get(
            "/helpers",
            query_string={"explicit": "yes"} if explicit else {},
            headers={"X-Prefix": prefix},
        )
        assert response.status_code == (422 if explicit else 200)
        assert response.text == (
            f"{prefix}:layout{prefix}:&lt;example&gt;{prefix}:partial"
        )

    assert get_actions(helpers_controller) == ["show"]


def test_render_uses_the_receiving_controllers_assigns_and_helpers(
    helper_app, helpers_controller
):
    with helper_app.test_request_context("/"):
        receiver = helpers_controller()
        receiver.prefix = "receiver"
        receiver.value = "body"
        ActionController()
        response = receiver.render("show")
        assert response.get_data(as_text=True) == (
            "receiver:layoutreceiver:bodyreceiver:partial"
        )


def test_controller_stream_partials_use_the_receiving_controllers_helpers(
    helper_app, helpers_controller
):
    with helper_app.test_request_context("/"):
        receiver = helpers_controller()
        receiver.prefix = "receiver"
        ActionController()
        response = receiver.render(
            turbo_stream=receiver.turbo_stream.update("label", partial="helpers/label")
        )
    assert response.mimetype == "text/vnd.turbo-stream.html"
    assert "<template>receiver:partial</template>" in response.get_data(as_text=True)


def test_helpers_are_scoped_to_the_current_controller(helper_app, helpers_controller):
    class UnrelatedController(ActionController):
        def show(self):
            return render_template("unrelated.html")

    init(UnrelatedController)
    helper_app.add_url_rule("/helpers", view_func=lambda: helpers_controller().show())
    helper_app.add_url_rule(
        "/unrelated",
        endpoint="unrelated",
        view_func=lambda: UnrelatedController().show(),
    )
    helper_app.add_url_rule(
        "/plain", endpoint="plain", view_func=lambda: render_template("unrelated.html")
    )
    client = helper_app.test_client()

    client.get("/helpers")
    assert client.get("/unrelated").text == "False|False"
    assert client.get("/plain").text == "False|False"
    with helper_app.app_context():
        assert render_template("unrelated.html") == "False|False"


def test_inherited_helpers_use_child_overrides_without_affecting_siblings(helper_app):
    class ParentController(ActionController):
        helper_method("_label")

        def show(self):
            return render_template("helpers/_label.html")

        def _label(self, value):
            return f"parent:{value}"

    init(ParentController)

    class ChildController(ParentController):
        def _label(self, value):
            return f"child:{value}"

    class SiblingController(ParentController):
        pass

    init(ChildController)
    init(SiblingController)
    helper_app.add_url_rule("/child", view_func=lambda: ChildController().show())
    helper_app.add_url_rule(
        "/sibling", endpoint="sibling", view_func=lambda: SiblingController().show()
    )
    helper_app.add_url_rule(
        "/parent", endpoint="parent", view_func=lambda: ParentController().show()
    )
    client = helper_app.test_client()

    assert client.get("/child").text == "child:partial"
    assert client.get("/sibling").text == "parent:partial"
    assert client.get("/parent").text == "parent:partial"


@pytest.mark.parametrize("method_name", ["label", "__label"])
def test_helpers_require_private_controller_methods(method_name):
    with pytest.raises(ProgrammerError, match="private methods"):

        class InvalidController(ActionController):
            helper_method(method_name)


@pytest.mark.parametrize("name", ["", "_label", "invalid-name"])
def test_helpers_require_public_template_names(name):
    with pytest.raises(ProgrammerError, match="public identifiers"):

        class InvalidController(ActionController):
            helper_method("_label", name=name)


def test_helpers_require_callable_methods():
    class InvalidController(ActionController):
        helper_method("_label")
        _label = "not callable"

    with pytest.raises(ProgrammerError, match="must be callable"):
        init(InvalidController)
