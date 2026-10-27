from functools import wraps

import pytest

from flaskteroids.actions import (
    after_action,
    around_action,
    before_action,
    skip_before_action,
)
from flaskteroids.controller import Controller
from flaskteroids.controller import init as init_controller
from flaskteroids.mailer import Mailer
from flaskteroids.mailer import init as init_mailer
from flaskteroids.rules import bind_rules, declaration


def test_rules_collect_local_declarations_once_through_diamond():
    events = []

    @declaration
    def record():
        def bind(cls):
            events.append(cls.__name__)

        return bind

    class Root:
        record()

    class Left(Root):
        record()

    class Right(Root):
        pass

    class Child(Left, Right):
        record()
        record()

    bind_rules(Root)
    bind_rules(Child)
    bind_rules(Child)
    assert events == ["Root", "Child", "Child", "Child", "Child"]


@pytest.mark.parametrize(
    "base,prepare", [(Controller, init_controller), (Mailer, init_mailer)]
)
def test_plain_mixin_diamonds_contribute_action_callbacks(base, prepare, app):
    events = []

    class Shared:
        before_action("_shared")

        def _shared(self):
            events.append("shared")

    class Left(Shared):
        pass

    class Right(Shared):
        pass

    class Example(Left, Right, base):
        def index(self):
            events.append("action")
            return (
                "response"
                if base is Controller
                else self.mail(to="a@example.com", subject="hello")
            )

    prepare(Example)
    with app.app_context():
        Example().index()
    assert events == ["shared", "action"]


@pytest.mark.parametrize(
    "base,prepare", [(Controller, init_controller), (Mailer, init_mailer)]
)
def test_inherited_actions_prepare_once_and_preserve_application_decorators(
    base, prepare, app
):
    events = []

    def application_decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            events.append("application")
            return fn(*args, **kwargs)

        return decorated

    class Parent(base):
        before_action("_before")
        after_action("_after")

        def _before(self):
            events.append("before")

        def _after(self):
            events.append("after")

        @application_decorator
        def index(self):
            events.append("action")
            return (
                "response"
                if base is Controller
                else self.mail(to="a@example.com", subject="hello")
            )

    prepare(Parent)

    class Child(Parent):
        skip_before_action("_before", only=["index"])
        before_action("_child", only=["index"])

        def _child(self):
            events.append("child")

    prepare(Child)
    prepare(Child)
    with app.app_context():
        result = Child().index()
        if base is Mailer:
            assert result.builder.template_name == "index"
    assert events == ["child", "application", "action", "after"]


@pytest.mark.parametrize(
    "base,prepare", [(Controller, init_controller), (Mailer, init_mailer)]
)
def test_explicit_super_action_runs_parent_chain(base, prepare, app):
    events = []

    class Parent(base):
        before_action("_before")

        def _before(self):
            events.append("before")

        def index(self):
            events.append("parent")
            return (
                "response"
                if base is Controller
                else self.mail(to="a@example.com", subject="hello")
            )

    prepare(Parent)

    class Child(Parent):
        def index(self):
            events.append("child")
            return super().index()

    prepare(Child)
    prepare(Parent)
    with app.app_context():
        Child().index()
    assert events == ["before", "child", "before", "parent"]


@pytest.mark.parametrize(
    "base,prepare", [(Controller, init_controller), (Mailer, init_mailer)]
)
def test_diamond_action_chains_apply_to_new_actions_and_overrides(base, prepare, app):
    events = []

    class Root(base):
        before_action("_all")
        around_action("_around")
        after_action("_after")

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

    class Left(Root):
        before_action("_left")

        def _left(self):
            events.append("left")

    class Right(Root):
        before_action("_right")

        def _right(self):
            events.append("right")

    prepare(Left)
    prepare(Right)

    class Child(Left, Right):
        skip_before_action("_left", only=["index"])
        before_action("_local")
        before_action("_local")

        def _local(self):
            events.append("local")

        def index(self):
            events.append("child")
            return (
                "response"
                if base is Controller
                else self.mail(to="a@example.com", subject="hello")
            )

        def extra(self):
            events.append("extra")
            return (
                "response"
                if base is Controller
                else self.mail(to="a@example.com", subject="hello")
            )

    prepare(Child)
    prepare(Child)
    with app.app_context():
        child = Child()
        child.index()
        result = child.extra()
        if base is Mailer:
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
