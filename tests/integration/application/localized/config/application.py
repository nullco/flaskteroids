from config.boot import ROOT

from flaskteroids.application import Application as FlaskteroidsApplication


class Application(FlaskteroidsApplication):
    root = ROOT

    def configure(self, config):
        config.load_defaults("0.1")
        config.i18n.available_locales = ["en", "es"]
        config.i18n.raise_on_missing_translations = True
