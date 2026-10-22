import pytest
from flask import current_app
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.controller import ActionController
from flaskteroids.helpers import form_with
from flaskteroids.model import (
    PasswordAuthenticator,
    has_secure_password,
    validates,
)
from tests.assertions import HTML
from tests.model.schema_support import model_base

Base = declarative_base()


class AccountTable(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    password_digest = Column(String)


class PasscodeAccountTable(Base):
    __tablename__ = "passcode_accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    password_digest = Column(String)
    passcode_digest = Column(String)


class Account(model_base(Base), PasswordAuthenticator):
    has_secure_password()
    validates("name", confirmation=True)


class PasscodeAccount(model_base(Base), PasswordAuthenticator):
    has_secure_password("passcode")
    validates("name", confirmation=True)


@pytest.fixture(params=["password", "passcode"])
def account_model(request, init_models):
    password_field = request.param
    table, model = (
        (AccountTable, Account)
        if password_field == "password"
        else (PasscodeAccountTable, PasscodeAccount)
    )
    init_models(Base, [(table, model)])
    return model, password_field


@pytest.fixture
def flask_app(account_model):
    return current_app._get_current_object()


@pytest.fixture
def json_response(flask_app):
    def response(value):
        with flask_app.test_request_context():
            return ActionController().render(json=value).get_json()

    return response


@pytest.mark.parametrize("state", ["new", "created", "loaded", "updated", "pending"])
def test_model_json_excludes_authentication_fields(account_model, json_response, state):
    account, password_field = account_model
    values = {
        "name": "Alice",
        "name_confirmation": "Alice",
        password_field: "secret-password",
        f"{password_field}_confirmation": "secret-password",
    }
    user = account.new(**values) if state == "new" else account.create(**values)
    if state == "loaded":
        user = account.find(user.id)
    elif state == "updated":
        assert user.update(
            **{
                password_field: "replacement-password",
                f"{password_field}_confirmation": "replacement-password",
            }
        )
    elif state == "pending":
        user.name = "Bob"
        setattr(user, password_field, "replacement-password")

    expected = {"id": user.id, "name": user.name}
    assert json_response(user) == expected
    assert json_response([user]) == [expected]
    assert json_response({"data": {"users": [user]}}) == {"data": {"users": [expected]}}


@pytest.mark.parametrize("state", ["new", "created", "loaded", "updated", "pending"])
def test_model_repr_displays_class_address_and_published_columns(account_model, state):
    account, password_field = account_model
    values = {"name": "Alice", password_field: "secret-password"}
    user = account.new(**values) if state == "new" else account.create(**values)
    published_name = None if state == "new" else "Alice"
    if state == "loaded":
        from flaskteroids.db import session

        identity = user.id
        session.expunge(user)
        user = account.find(identity)
    elif state == "updated":
        assert user.update(name="Bob")
        published_name = "Bob"
    elif state == "pending":
        user.name = "Unsaved name"
        setattr(user, password_field, "replacement-password")

    expected = {"id": user.id, "name": published_name}
    assert repr(user) == f"<{account.__name__}:{hex(id(user))} {expected}>"


def test_model_repr_excludes_credentials_and_leaves_reset_tokens_lazy(
    account_model, mocker
):
    account, password_field = account_model
    user = account.create(name="Alice", **{password_field: "secret-password"})
    dumps = mocker.spy(URLSafeTimedSerializer, "dumps")

    representation = repr(user)

    dumps.assert_not_called()
    assert "secret-password" not in representation
    assert getattr(user, f"{password_field}_digest") not in representation
    assert "password_digest" not in representation
    assert "passcode_digest" not in representation


def test_model_repr_uses_published_columns_independently_of_json_customization(
    account_model, mocker
):
    account, _ = account_model
    mocker.patch.object(account, "__json__", return_value={"response": "custom"})
    user = account.create(name="Alice")
    expected = {"id": user.id, "name": "Alice"}

    assert repr(user) == f"<{account.__name__}:{hex(id(user))} {expected}>"


def test_model_list_preserves_order_and_input(account_model, json_response):
    account, _ = account_model
    first = account.new(name="Alice")
    second = account.new(name="Bob")
    users = [second, first, second]

    assert json_response(users) == [
        {"id": None, "name": "Bob"},
        {"id": None, "name": "Alice"},
        {"id": None, "name": "Bob"},
    ]
    assert users == [second, first, second]


def test_query_json_excludes_authentication_fields(account_model, json_response):
    account, password_field = account_model
    user = account.create(name="Alice", **{password_field: "secret-password"})

    expected = [{"id": user.id, "name": "Alice"}]
    assert json_response(account.all()) == expected
    assert json_response({"users": account.all()}) == {"users": expected}


def test_json_serialization_leaves_reset_tokens_lazy(
    account_model, json_response, mocker
):
    account, password_field = account_model
    user = account.create(name="Alice", **{password_field: "secret-password"})
    dumps = mocker.spy(URLSafeTimedSerializer, "dumps")

    json_response(user)
    json_response(account.all())
    json_response([user])
    json_response({"users": [user], "query": account.all()})

    dumps.assert_not_called()
    token = getattr(user, f"{password_field}_reset_token")
    assert account.find_by_password_reset_token(token).id == user.id
    assert json_response(user) == {"id": user.id, "name": "Alice"}
    dumps.assert_called_once()


def test_json_serialization_applies_custom_model_protocol(
    account_model, json_response, mocker
):
    account, password_field = account_model

    def serialize(self):
        data = super(account, self).__json__()
        return {"display_name": data["name"]}

    mocker.patch.object(account, "__json__", serialize)
    user = account.create(name="Alice", **{password_field: "secret-password"})

    assert json_response(user) == {"display_name": "Alice"}
    assert json_response(account.all()) == [{"display_name": "Alice"}]
    assert json_response([user]) == [{"display_name": "Alice"}]
    assert json_response({"users": [user]}) == {"users": [{"display_name": "Alice"}]}


@pytest.mark.parametrize("persisted", [False, True])
def test_forms_render_staged_values_independently_of_response_serialization(
    account_model, flask_app, mocker, persisted
):
    account, password_field = account_model
    mocker.patch.object(
        account, "__json__", lambda self: {"public_name": "Not form data"}
    )
    values = {
        "name": "Alice",
        "name_confirmation": "Alice",
        password_field: "secret-password",
    }
    user = account.create(**values) if persisted else account.new(**values)
    if persisted:
        getattr(user, f"{password_field}_reset_token")
    user.name = "Bob"
    user.name_confirmation = "Bob"
    dumps = mocker.spy(URLSafeTimedSerializer, "dumps")

    with flask_app.test_request_context():
        html = form_with(
            model=user,
            url="/accounts",
            caller=lambda form: (
                form.text_field("name") + form.text_field("name_confirmation")
            ),
        )

    fields = [attrs for tag, attrs in HTML(html).elements if tag == "input"]
    assert sum(field.get("value") == "Bob" for field in fields) == 2
    assert "Not form data" not in html
    dumps.assert_called_once()
    assert dumps.call_args.kwargs == {"salt": "csrf-token"}
