import logging
import inspect
import pkgutil
from importlib import import_module
from flaskteroids.mailer import Mailer

_logger = logging.getLogger(__name__)


class MailExtension:

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        if not hasattr(app, "extensions") or 'flaskteroids.jobs' not in app.extensions:
            raise ValueError('Jobs extension not initialized')

        self._jobs_extension = app.extensions['flaskteroids.jobs']
        self._mailers = self._discover_mailers()

        for mailer_name, mailer_class in self._mailers.items():
            self.register_mailer(mailer_name, mailer_class)

        app.extensions["flaskteroids.mail"] = self

    def _discover_mailers(self):
        root_module_name = 'app.mailers'
        try:
            package = import_module(root_module_name)
        except ModuleNotFoundError:
            _logger.debug(f'No {root_module_name} module detected... ignoring')
            return {}
        package_path = package.__path__
        entries = {}
        for _, module_name, _ in pkgutil.iter_modules(package_path):
            absolute_name = f"{root_module_name}.{module_name}"
            module = import_module(absolute_name)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Mailer) and \
                        obj is not Mailer:
                    entries[name] = obj
        _logger.debug(f'discovered {len(entries)} classes in {root_module_name}')
        return entries

    def register_mailer(self, mailer_name, mailer_class):
        self._jobs_extension.register_job(mailer_name, mailer_class)
