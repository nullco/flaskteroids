import pytest
from sqlalchemy import create_engine, inspect

from tests.generated_application import cleanup_database


def test_batched_generation_boots_fresh_and_cleans_an_explicit_database(
    generated_app_factory, tmp_path, monkeypatch
):
    url = f"sqlite:///{tmp_path / 'shared.sqlite'}"
    monkeypatch.setenv("FLASKTEROIDS_DATABASE_URL", url)
    root, run = generated_app_factory("batch")
    run(
        commands=[
            ("generate", "model", "Author", "name:string"),
            ("generate", "model", "Story", "author:references", "title:string"),
        ]
    )
    run("db:prepare")
    engine = create_engine(url)
    try:
        assert {"authors", "stories"} <= set(inspect(engine).get_table_names())
        cleanup_database(root, run)
        assert not {"authors", "stories"} & set(inspect(engine).get_table_names())
        run("db:prepare")
        assert {"authors", "stories"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_batched_commands_stop_after_a_failure(generated_app_factory):
    root, run = generated_app_factory("failed_batch")
    with pytest.raises(AssertionError, match="unknown-command"):
        run(
            commands=[
                ("generate", "model", "Author", "name:string"),
                ("unknown-command",),
                ("generate", "model", "Story", "title:string"),
            ]
        )
    assert (root / "app/models/author.py").is_file()
    assert not (root / "app/models/story.py").exists()


def test_default_database_cleanup_preserves_disposable_app_files(
    generated_app_factory, monkeypatch
):
    monkeypatch.delenv("FLASKTEROIDS_DATABASE_URL", raising=False)
    root, run = generated_app_factory("disposable")
    run("generate", "model", "Author", "name:string")
    run("db:prepare")
    cleanup_database(root, run)
    engine = create_engine(f"sqlite:///{root / 'storage/test.sqlite3'}")
    try:
        assert "authors" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
