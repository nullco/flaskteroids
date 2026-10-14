import subprocess
import sys

import pytest

from flaskteroids import model

PUBLIC_NAMES = {
    "Error",
    "Errors",
    "Model",
    "ModelMeta",
    "ModelQuery",
    "PasswordAuthenticator",
    "RecordNotFoundException",
    "Relation",
    "after_commit",
    "after_create",
    "after_destroy",
    "after_find",
    "after_initialize",
    "after_rollback",
    "after_save",
    "after_update",
    "after_validation",
    "around_create",
    "around_destroy",
    "around_save",
    "around_update",
    "before_create",
    "before_destroy",
    "before_save",
    "before_update",
    "before_validation",
    "belongs_to",
    "has_many",
    "has_many_attached",
    "has_one_attached",
    "has_secure_password",
    "init",
    "validates",
}
CONFIG_NAMES = {"PresenceConfig", "LengthConfig", "ComparisonConfig"}


def test_length_config():
    from flaskteroids.model import LengthConfig

    assert not hasattr(model, "LenghtConfig")
    assert LengthConfig(minimum=1, maximum=72) == {"minimum": 1, "maximum": 72}


def test_existing_public_model_imports():
    assert PUBLIC_NAMES <= set(model.__all__)
    for name in PUBLIC_NAMES | CONFIG_NAMES:
        assert getattr(model, name) is not None


@pytest.mark.parametrize(
    "first_import",
    [
        "flaskteroids.model",
        "flaskteroids.extensions.db",
        "flaskteroids.application",
        "flaskteroids._models.validation",
        "flaskteroids._models.authentication",
        "flaskteroids._models.associations",
        "flaskteroids._models.records",
        "flaskteroids._models.query",
    ],
)
def test_model_imports_without_app_context_in_fresh_process(first_import):
    script = f"""
import importlib
from unittest.mock import patch
from flask import has_app_context
with patch("sqlalchemy.create_engine") as database, patch("celery.Celery") as queue:
    importlib.import_module({first_import!r})
    database.assert_not_called()
    queue.assert_not_called()
from flaskteroids.model import *
from flaskteroids.model import PresenceConfig, LengthConfig, ComparisonConfig
class ApplicationModel(Model):
    pass
class User(ApplicationModel, PasswordAuthenticator):
    pass
assert not has_app_context()
assert ModelQuery is not None and Relation is not None
"""
    subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
