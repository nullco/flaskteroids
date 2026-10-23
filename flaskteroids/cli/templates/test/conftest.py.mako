import os

os.environ.setdefault("FLASKTEROIDS_ENV", "test")

pytest_plugins = ["flaskteroids.testing.pytest_plugin"]
