import os

os.environ.setdefault("FLASK_ENV", "test")

pytest_plugins = ["flaskteroids.testing.pytest_plugin"]
