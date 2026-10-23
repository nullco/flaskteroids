import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from flaskteroids.encryption import generate_encryption_key
from tests.assertions import assert_pytest_passed


@pytest.fixture(scope="module")
def rich_text_application(generated_app_factory):
    root, run = generated_app_factory("writing")
    run("db:create")
    run("generate", "scaffold", "Post", "title:string", "content:rich_text")
    run("rich_text:install")
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
    asset = root / "app/assets/rich_text/rich_text.css"
    asset.write_text("/* application styles */")
    run("rich_text:install")
    assert layout.read_text() == installed
    assert asset.read_text() == "/* application styles */"
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


def test_generated_rich_text_browser_workflow(generated_app_factory):
    root, run = generated_app_factory("writing_browser")
    run("rich_text:install")
    run("generate", "scaffold", "Post", "title:string", "content:rich_text")
    source = Path(__file__).parent / "fixtures/rich_text"
    shutil.copyfile(source / "post.py", root / "app/models/post.py")
    shutil.copyfile(source / "writing.py", root / "test/system/writing_test.py")
    shutil.copyfile(source / "vendor/turbo.js", root / "app/assets/rich_text/turbo.js")
    layout = root / "app/views/layouts/application.html"
    layout.write_text(
        layout.read_text().replace(
            "https://cdn.jsdelivr.net/npm/@hotwired/turbo@latest/dist/turbo.es2017-esm.min.js",
            "{{ asset_path('rich_text/turbo.js') }}",
        )
    )
    report = root / "rich-text-browser.xml"
    run("test:system", "-q", "--junitxml", str(report), "test/system/writing_test.py")
    assert_pytest_passed(report)


def test_encrypted_scaffold_fixtures_and_controller_workflows(generated_app_factory):
    root, run = generated_app_factory("writing_encrypted")
    run("rich_text:install")
    run("generate", "scaffold", "Post", "title:string", "content:rich_text")
    source = Path(__file__).parent / "fixtures/rich_text"
    shutil.copyfile(source / "encrypted_post.py", root / "app/models/post.py")
    shutil.copyfile(source / "requests.py", root / "test/controllers/rich_text_test.py")
    (root / "config/initializers/rich_text.py").write_text(
        "from flask import current_app\n"
        f"current_app.config.active_record.encryption.primary_key = {generate_encryption_key()!r}\n"
    )
    report = root / "encrypted-rich-text.xml"
    run("test", "-q", "--junitxml", str(report))
    assert_pytest_passed(report)


def test_rich_text_assets_compile_without_a_javascript_toolchain(rich_text_application):
    root, run = rich_text_application
    run("assets:precompile")
    assert list((root / "public/assets/rich_text").glob("trix-*.js"))
    assert list((root / "public/assets/rich_text").glob("trix-*.css"))
