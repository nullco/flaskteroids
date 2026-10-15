from pathlib import Path

from sqlalchemy.engine import URL, Engine, make_url

from flaskteroids.cli.db.config import get_config


def test_root_relative_resources_and_literal_percent_urls_need_no_database_io(
    app, tmp_path, monkeypatch, mocker
):
    root = tmp_path / "100% custom root"
    url = URL.create(
        "postgresql+psycopg",
        username="user",
        password="p@%:/?!",
        host="localhost",
        database="db%:name",
    )
    monkeypatch.setattr(app, "project_root", root)
    monkeypatch.setattr(app, "database_url", url.render_as_string(hide_password=False))
    connect = mocker.patch.object(
        Engine, "connect", side_effect=AssertionError("unexpected connection")
    )
    with app.app_context():
        config = get_config()
        assert Path(config.config_file_name) == root / "db/migrate/alembic.ini"
        assert Path(config.get_main_option("script_location")) == root / "db/migrate"
        assert make_url(config.get_main_option("sqlalchemy.url")) == url
        assert Path(config.get_template_directory()).is_dir()
    connect.assert_not_called()
