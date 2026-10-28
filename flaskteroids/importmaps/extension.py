"""Application lifecycle integration; development evaluates fresh configuration."""

from flask import current_app, request

from flaskteroids.assets import asset_path
from flaskteroids.importmaps.map import ImportMap


class ImportmapExtension:
    def __init__(self, app):
        self.app = app
        self.map = ImportMap.load(app.project_root)
        self._resolved = {}

    def resolve(self):
        development = self.app.env.development or self.app.env.test
        key = request.script_root
        if not development and key in self._resolved:
            return self._resolved[key]
        importmap = ImportMap.load(self.app.project_root) if development else self.map
        pipeline = self.app.extensions["flaskteroids.assets"]

        def integrity(name):
            return pipeline.asset_integrity(name, compiled=not development)

        resolved = importmap.resolve(asset_path, integrity_resolver=integrity)
        if not development:
            self._resolved[key] = resolved
        return resolved


def init_importmaps(app):
    app.extensions["flaskteroids.importmap"] = ImportmapExtension(app)


def resolved_importmap():
    return current_app.extensions["flaskteroids.importmap"].resolve()
