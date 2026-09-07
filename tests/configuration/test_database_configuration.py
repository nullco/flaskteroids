from flaskteroids.database_configuration import load_database_configuration


def write_database_config(tmp_path, content):
    config = tmp_path / "config"
    config.mkdir()
    (config / "database.yml").write_text(content)


def test_loads_selected_database_environment(tmp_path):
    write_database_config(
        tmp_path,
        """
default: &default
  adapter: sqlite3
  pool: 5
development:
  <<: *default
  database: storage/development.sqlite3
test:
  <<: *default
  database: storage/test.sqlite3
""",
    )

    result = load_database_configuration(tmp_path, "test", environ={})

    assert result["url"] == "sqlite:///storage/test.sqlite3"
    assert result["selected"]["pool"] == 5


def test_database_url_overrides_individual_configuration_values(tmp_path):
    write_database_config(
        tmp_path,
        """
production:
  adapter: postgresql
  database: configured_database
""",
    )

    result = load_database_configuration(
        tmp_path,
        "production",
        environ={"DATABASE_URL": "postgresql://example/environment_database"},
    )

    assert result["url"] == "postgresql://example/environment_database"


def test_explicit_url_ignores_database_url_environment_variable(tmp_path):
    write_database_config(
        tmp_path,
        """
production:
  url: postgresql://example/configured_database
""",
    )

    result = load_database_configuration(
        tmp_path,
        "production",
        environ={"DATABASE_URL": "postgresql://example/environment_database"},
    )

    assert result["url"] == "postgresql://example/configured_database"


def test_interpolates_environment_variables(tmp_path):
    write_database_config(
        tmp_path,
        """
production:
  adapter: postgresql
  database: ${DATABASE_NAME}
  username: ${DATABASE_USER:-postgres}
""",
    )

    result = load_database_configuration(
        tmp_path,
        "production",
        environ={"DATABASE_NAME": "flaskteroids"},
    )

    assert result["url"] == "postgresql://postgres@/flaskteroids"
