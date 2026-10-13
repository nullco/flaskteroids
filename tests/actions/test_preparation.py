from functools import wraps

import pytest
from flask import Flask

from flaskteroids.actions import (
    after_action,
    around_action,
    before_action,
    skip_before_action,
)
from flaskteroids.controller import ActionController
from flaskteroids.controller import init as init_controller
from flaskteroids.mailer import ActionMailer
from flaskteroids.mailer import init as init_mailer
from flaskteroids.rules import bind_rules, rules


def test_rules_collect_local_declarations_once_through_diamond():
    events = []

    def record(cls):
        events.append(cls.__name__)

    @rules(record)
    class Root:
        pass

    @rules(record)
    class Left(Root):
        pass

    class Right(Root):
        pass

    @rules(record, record)
    class Child(Left, Right):
        pass

    bind_rules(Root)
    bind_rules(Child)
    bind_rules(Child)
    assert events == ["Root", "Child", "Child", "Child", "Child"]


@pytest.mark.parametrize(
    "base,prepare", [(ActionController, init_controller), (ActionMailer, init_mailer)]
)
def test_inherited_actions_prepare_once_and_preserve_application_decorators(
    base, prepare
):
    events = []

    def application_decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            events.append("application")
            return fn(*args, **kwargs)

        return decorated

    @rules(before_action("_before"), after_action("_after"))
    class Parent(base):
        def _before(self):
            events.append("before")

        def _after(self):
            events.append("after")

        @application_decorator
        def index(self):
            events.append("action")
            return (
                "response"
                if base is ActionController
                else self.mail(to="a@example.com", subject="hello")
            )

    prepare(Parent)

    @rules(
        skip_before_action("_before", only=["index"]),
        before_action("_child", only=["index"]),
    )
    class Child(Parent):
        def _child(self):
            events.append("child")

    prepare(Child)
    prepare(Child)
    app = Flask(__name__)
    app.config.action_mailer = type("MailConfig", (), {"default_options": {}})()
    with app.app_context():
        result = Child().index()
        if base is ActionMailer:
            assert result.builder.template_name == "index"
    assert events == ["child", "application", "action", "after"]


@pytest.mark.parametrize(
    "base,prepare", [(ActionController, init_controller), (ActionMailer, init_mailer)]
)
def test_explicit_super_action_runs_parent_chain(base, prepare):
    events = []

    @rules(before_action("_before"))
    class Parent(base):
        def _before(self):
            events.append("before")

        def index(self):
            events.append("parent")
            return (
                "response"
                if base is ActionController
                else self.mail(to="a@example.com", subject="hello")
            )

    prepare(Parent)

    class Child(Parent):
        def index(self):
            events.append("child")
            return super().index()

    prepare(Child)
    prepare(Parent)
    app = Flask(__name__)
    app.config.action_mailer = type("MailConfig", (), {"default_options": {}})()
    with app.app_context():
        Child().index()
    assert events == ["before", "child", "before", "parent"]


@pytest.mark.parametrize(
    "base,prepare", [(ActionController, init_controller), (ActionMailer, init_mailer)]
)
def test_diamond_action_chains_apply_to_new_actions_and_overrides(base, prepare):
    events = []

    @rules(before_action("_all"), around_action("_around"), after_action("_after"))
    class Root(base):
        def _all(self):
            events.append("all")

        def _around(self):
            events.append("enter")
            yield
            events.append("exit")

        def _after(self):
            events.append("after")

        def index(self):
            events.append("root")
            return "response"

    prepare(Root)

    @rules(before_action("_left"))
    class Left(Root):
        def _left(self):
            events.append("left")

    @rules(before_action("_right"))
    class Right(Root):
        def _right(self):
            events.append("right")

    prepare(Left)
    prepare(Right)

    @rules(
        skip_before_action("_left", only=["index"]),
        before_action("_local"),
        before_action("_local"),
    )
    class Child(Left, Right):
        def _local(self):
            events.append("local")

        def index(self):
            events.append("child")
            return (
                "response"
                if base is ActionController
                else self.mail(to="a@example.com", subject="hello")
            )

        def extra(self):
            events.append("extra")
            return (
                "response"
                if base is ActionController
                else self.mail(to="a@example.com", subject="hello")
            )

    prepare(Child)
    prepare(Child)
    app = Flask(__name__)
    app.config.action_mailer = type("MailConfig", (), {"default_options": {}})()
    with app.app_context():
        child = Child()
        child.index()
        result = child.extra()
        if base is ActionMailer:
            assert result.builder.template_name == "extra"
    assert events == [
        "all",
        "right",
        "local",
        "local",
        "enter",
        "child",
        "exit",
        "after",
        "all",
        "left",
        "right",
        "local",
        "local",
        "enter",
        "extra",
        "exit",
        "after",
    ]
