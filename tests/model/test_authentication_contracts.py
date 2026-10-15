import pytest
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base
from werkzeug.security import check_password_hash

from flaskteroids.model import PasswordAuthenticator, has_secure_password
from flaskteroids.rules import rules
from tests.model.schema_support import model_base

Base = declarative_base()


class AccountTable(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    password_digest = Column(String)
    passcode_digest = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


@pytest.fixture(params=["password", "passcode"])
def account_model(request, init_models):
    @rules(has_secure_password(request.param))
    class Account(model_base(Base), PasswordAuthenticator):
        pass

    init_models(Base, [(AccountTable, Account)])
    return Account, request.param


def test_loaded_password_updates_and_confirmation(account_model):
    Account, field = account_model
    account = Account.create(name="one", **{field: "secret"})
    loaded = Account.find(account.id)
    assert loaded.update(name="two") is True
    assert loaded.authenticate("secret")
    assert (
        loaded.update(**{field: "changed", f"{field}_confirmation": "wrong"}) is False
    )
    assert loaded.update(**{f"{field}_confirmation": "changed"}) is True
    assert Account.find(account.id).authenticate("changed")


def test_missing_user_still_checks_hash(account_model, mocker):
    Account, field = account_model
    check = mocker.patch(
        "flaskteroids._models.authentication.check_password_hash",
        wraps=check_password_hash,
    )
    assert Account.authenticate_by(name="absent", **{field: "secret"}) is None
    check.assert_called_once_with("a", "b")
