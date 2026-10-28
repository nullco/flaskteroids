import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from flaskteroids.encryption import generate_encryption_key
from tests.assertions import assert_pytest_passed


@pytest.fixture(scope="module")
def rich_text_application(generated_app_factory):
    root, run = generated_app_factory("writing")
    run(
        commands=[
            ("db:create",),
            ("generate", "scaffold", "Post", "title:string", "content:rich_text"),
            ("rich_text:install",),
        ]
    )
    return root, run


def test_install_preserves_customizations_and_generates_reversible_storage(
    generated_app_factory,
):
    root, run = generated_app_factory("rich_text_install")
    layout = root / "app/views/layouts/application.html"
    marker = '<meta name="application-marker" content="preserve">'
    layout.write_text(layout.read_text().replace("</head>", marker + "\n</head>"))
    run("rich_text:install")
    installed = layout.read_text()
    migrations = set((root / "db/migrate/versions").glob("*.py"))
    assert marker in installed
    asset = root / "app/assets/rich_text.css"
    asset.write_text("/* application styles */")
    entrypoint = root / "app/javascript/application.js"
    configured_javascript = entrypoint.read_text()
    pins = (root / "config/importmap.py").read_text()
    run("rich_text:install")
    assert layout.read_text() == installed
    assert asset.read_text() == "/* application styles */"
    assert entrypoint.read_text() == configured_javascript
    assert (root / "config/importmap.py").read_text() == pins
    assert not (root / "app/assets/lexxy.js").exists()
    assert set((root / "db/migrate/versions").glob("*.py")) == migrations
    run("db:migrate")
    engine = create_engine(f"sqlite:///{root / 'storage/test.sqlite3'}")
    try:
        assert {"rich_texts", "attachment_blobs", "record_attachments"} <= set(
            inspect(engine).get_table_names()
        )
        assert inspect(engine).get_indexes("rich_texts")[0]["unique"]
        run("db:rollback")
        assert "rich_texts" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_generated_rich_text_scaffold_passes_controller_and_model_tests(
    rich_text_application,
):
    root, run = rich_text_application
    source = Path(__file__).parent / "fixtures/rich_text/requests.py"
    shutil.copyfile(source, root / "test/controllers/rich_text_test.py")
    report = root / "rich-text-tests.xml"
    run("test", "-q", "--junitxml", str(report))
    assert_pytest_passed(report)


@pytest.mark.system
def test_generated_rich_text_browser_workflow(generated_app_factory):
    root, run = generated_app_factory("writing_browser")
    run(
        commands=[
            ("rich_text:install",),
            ("generate", "scaffold", "Post", "title:string", "content:rich_text"),
        ]
    )
    source = Path(__file__).parent / "fixtures/rich_text"
    shutil.copyfile(source / "post.py", root / "app/models/post.py")
    shutil.copyfile(source / "writing.py", root / "test/system/writing_test.py")
    report = root / "rich-text-browser.xml"
    run("test:system", "-q", "--junitxml", str(report), "test/system/writing_test.py")
    assert_pytest_passed(report)


def test_encrypted_scaffold_fixtures_and_controller_workflows(generated_app_factory):
    root, run = generated_app_factory("writing_encrypted")
    run(
        commands=[
            ("rich_text:install",),
            ("generate", "scaffold", "Post", "title:string", "content:rich_text"),
        ]
    )
    source = Path(__file__).parent / "fixtures/rich_text"
    shutil.copyfile(source / "encrypted_post.py", root / "app/models/post.py")
    shutil.copyfile(source / "requests.py", root / "test/controllers/rich_text_test.py")
    (root / "config/initializers/rich_text.py").write_text(
        "from flask import current_app\n"
        f"current_app.config.encryption.primary_key = {generate_encryption_key()!r}\n"
    )
    report = root / "encrypted-rich-text.xml"
    run("test", "-q", "--junitxml", str(report))
    assert_pytest_passed(report)


@pytest.mark.system
@pytest.mark.parametrize("environment", ["development", "production"])
def test_packaged_editor_and_uploads_work_without_external_assets(
    rich_text_application, environment
):
    _, run = rich_text_application
    run(commands=[("db:prepare",), ("assets:precompile",)])
    script = Path(__file__).parent / "fixtures/rich_text/assets.py"
    run(environment, script=str(script))


def test_rich_text_assets_compile_without_a_javascript_toolchain(rich_text_application):
    root, run = rich_text_application
    run("assets:precompile")
    manifest = json.loads((root / "public/assets/.manifest.json").read_text())
    for name in ("lexxy.js", "lexxy.css", "rich_text.js", "rich_text_uploads.js"):
        assert (root / "public/assets" / manifest[name]).is_file()
    css = (root / "public/assets" / manifest["lexxy.css"]).read_text()
    assert manifest["lexxy-content.css"] in css
    assert manifest["lexxy-editor.css"] in css
