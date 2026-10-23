import base64
import shutil
from pathlib import Path

import yaml

from flaskteroids.credentials import Credentials, encrypt
from tests.assertions import assert_pytest_passed


def test_encryption_key_command_prints_distinct_keys_without_changing_credentials(
    cli_runner, app, tmp_path
):
    app.credentials = Credentials(tmp_path, "test", environ={})
    app.credentials.content_path.parent.mkdir(parents=True)
    original = b"existing credentials"
    app.credentials.content_path.write_bytes(original)
    result = cli_runner.invoke(args=["db:encryption:init"])
    assert result.exit_code == 0, result.output
    keys = yaml.safe_load(result.output)["active_record_encryption"]
    assert set(keys) == {"primary_key", "deterministic_key"}
    assert len({*keys.values()}) == 2
    assert all(len(base64.urlsafe_b64decode(key)) == 32 for key in keys.values())
    assert app.credentials.content_path.read_bytes() == original


def test_generated_encrypted_models_support_fixtures_forms_and_requests(
    generated_app_factory,
):
    root, run = generated_app_factory("encrypted_accounts")
    generated_keys = yaml.safe_load(run("db:encryption:init").stdout)
    credentials = Credentials(root, "test", environ={})
    values = credentials.to_dict() | generated_keys
    key = credentials.key()
    assert key is not None
    credentials.content_path.write_text(encrypt(yaml.safe_dump(values), key))
    run("generate", "scaffold", "Account", "name:string", "email:text", "notes:text")
    source = Path(__file__).parent / "fixtures/encryption"
    shutil.copyfile(source / "account.py", root / "app/models/account.py")
    shutil.copyfile(
        source / "requests.py", root / "test/controllers/encryption_test.py"
    )
    report = root / "encryption-tests.xml"
    run("test", "-q", "--junitxml", str(report))
    assert_pytest_passed(report)
