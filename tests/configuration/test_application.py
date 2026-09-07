import sys
import types
import pytest
from flaskteroids.application import Application
from flaskteroids.credentials import CredentialsError, encrypt, generate_key


@pytest.fixture
def routes_module(monkeypatch):
    module = types.ModuleType("test_configuration_routes")
    module.register = lambda routes: None
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module.__name__


def application_class(routes_module):
    class TestApplication(Application):
        def configure(self, config):
            config.load_defaults("0.1")
            config.paths.routes = routes_module
            config.paths.models = "missing.models"
            config.paths.controllers = "missing.controllers"
            config.paths.jobs = "missing.jobs"
            config.paths.mailers = "missing.mailers"
            config.x.application_value = "application"

        def _configure_database(self):
            self.database_url = "sqlite:///:memory:"

    return TestApplication


def test_loads_environment_configuration(tmp_path, routes_module):
    environment_path = tmp_path / "config" / "environments"
    environment_path.mkdir(parents=True)
    (environment_path / "test.py").write_text("""
def configure(config):
    config.enable_reloading = True
    config.x.application_value = 'test'
""")

    app = application_class(routes_module).initialize(
        environment="test", root_path=tmp_path
    )

    assert app.env.test
    assert app.env.name == "test"
    assert app.config.defaults_version == "0.1"
    assert app.config.enable_reloading
    assert app.config.x.application_value == "test"


def test_uses_environment_variable_to_select_environment(
    tmp_path, routes_module, monkeypatch
):
    monkeypatch.setenv("FLASKTEROIDS_ENV", "test")

    app = application_class(routes_module).initialize(root_path=tmp_path)

    assert app.env.test


def test_runs_initializers_in_filename_order(tmp_path, routes_module):
    initializers = tmp_path / "config" / "initializers"
    initializers.mkdir(parents=True)
    (initializers / "02_second.py").write_text(
        "from flaskteroids import application\n"
        "application.config.x.order += ['second']\n"
    )
    (initializers / "01_first.py").write_text(
        "from flaskteroids import application\napplication.config.x.order = ['first']\n"
    )

    app = application_class(routes_module).initialize(
        environment="test", root_path=tmp_path
    )

    assert app.config.x.order == ["first", "second"]


def test_loads_secret_key_base_from_credentials(tmp_path, routes_module):
    config_path = tmp_path / "config"
    config_path.mkdir()
    key = generate_key()
    (config_path / "master.key").write_text(key)
    (config_path / "credentials.yml.enc").write_text(
        encrypt("secret_key_base: shared-secret\n", key)
    )

    app = application_class(routes_module).initialize(
        environment="test", root_path=tmp_path
    )

    assert app.secret_key == "shared-secret"
    assert app.credentials.secret_key_base == "shared-secret"


def test_production_requires_secret_key_base(tmp_path, routes_module):
    with pytest.raises(CredentialsError, match="secret_key_base"):
        application_class(routes_module).initialize(
            environment="production", root_path=tmp_path
        )
