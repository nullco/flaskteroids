import importlib
import sys
from types import ModuleType
from unittest.mock import patch

from flask import has_app_context


def main(first_import):
    with patch("sqlalchemy.create_engine") as database, patch("celery.Celery") as queue:
        importlib.import_module(first_import)
        database.assert_not_called()
        queue.assert_not_called()

    import sqlalchemy as sa
    from sqlalchemy import inspect

    from flaskteroids.model import Model, ModelQuery, PasswordAuthenticator
    from flaskteroids.schema import Snapshot

    schema = ModuleType("import_test_schema")
    snapshot = Snapshot()
    snapshot.create_table("users", sa.Column("id", sa.Integer(), primary_key=True))
    schema.metadata = snapshot.metadata

    class ApplicationModel(Model):
        __abstract__ = True
        __schema_module__ = schema.__name__

    class User(ApplicationModel, PasswordAuthenticator):
        pass

    assert not has_app_context()
    assert "__mapper__" not in vars(User)
    assert schema.__name__ not in sys.modules
    sys.modules[schema.__name__] = schema
    with patch(
        "sqlalchemy.engine.Engine.connect",
        side_effect=AssertionError("unexpected connection"),
    ):
        assert User.prepare() is User
        assert inspect(User).class_ is User
    assert not hasattr(schema, "User")
    assert ModelQuery is not None


if __name__ == "__main__":
    main(sys.argv[1])
