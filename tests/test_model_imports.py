import subprocess
import sys
from pathlib import Path

import pytest

from flaskteroids import model

PUBLIC_NAMES = {
    "Error",
    "Errors",
    "Model",
    "ModelQuery",
    "PasswordAuthenticator",
    "RecordNotFoundException",
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
    "has_one",
    "has_many_attached",
    "has_one_attached",
    "has_secure_password",
    "init",
    "validates",
}
CONFIG_NAMES = {"PresenceConfig", "LengthConfig", "ComparisonConfig"}


def test_length_config_exposes_minimum_and_maximum():
    from flaskteroids.model import LengthConfig

    assert LengthConfig(minimum=1, maximum=72) == {"minimum": 1, "maximum": 72}


def test_model_exports_public_api_and_configuration_types():
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
        "flaskteroids._models.mapping",
        "flaskteroids._models.staging",
        "flaskteroids._models.query",
    ],
)
def test_model_imports_and_preparation_work_in_standalone_processes(first_import):
    script = Path(__file__).parent / "fixtures/model_imports.py"
    result = subprocess.run(
        [sys.executable, str(script), first_import],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
