import pytest

from flaskteroids.application import Application


@pytest.fixture
def asset_root(tmp_path):
    for folder in ("stylesheets", "images"):
        (tmp_path / "app/assets" / folder).mkdir(parents=True)
    (tmp_path / "app/assets/stylesheets/application.css").write_text(
        "body { color: red; }"
    )
    (tmp_path / "app/assets/images/logo.png").write_bytes(b"image bytes")
    (tmp_path / "app/assets/images/.keep").touch()
    (tmp_path / "private.txt").write_text("private")
    return tmp_path


@pytest.fixture
def asset_application(asset_root, discovery_package):
    package = discovery_package(
        {"__init__.py": "", "routes.py": "def register(route): pass"}
    )

    def create(environment="development", *, flask_config=None, **options):
        class TestApplication(Application):
            def configure(self, config):
                config.paths.routes = f"{package}.routes"
                for name in ("models", "controllers", "jobs", "mailers"):
                    setattr(config.paths, name, f"{package}.{name}")
                config.secret_key_base = "test"
                if environment not in ("development", "test"):
                    config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000
                config.update(flask_config or {})
                for name, value in options.items():
                    setattr(config.assets, name, value)

            def _configure_database(self):
                self.database_url = "sqlite:///:memory:"

        app = TestApplication.initialize(environment=environment, root_path=asset_root)
        app.testing = True
        return app

    return create
