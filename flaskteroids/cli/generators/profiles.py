"""The application-selected generator family."""

from dataclasses import dataclass
from types import ModuleType

from flaskteroids.cli.generators.authentication import api as api_authentication
from flaskteroids.cli.generators.authentication import (
    generator as browser_authentication,
)
from flaskteroids.cli.generators.controller import api as api_controller
from flaskteroids.cli.generators.controller import generator as browser_controller
from flaskteroids.cli.generators.scaffold import api as api_scaffold
from flaskteroids.cli.generators.scaffold import generator as browser_scaffold


@dataclass(frozen=True)
class Generators:
    controller: ModuleType
    scaffold: ModuleType
    authentication: ModuleType


BROWSER_GENERATORS = Generators(
    controller=browser_controller,
    scaffold=browser_scaffold,
    authentication=browser_authentication,
)
API_GENERATORS = Generators(
    controller=api_controller,
    scaffold=api_scaffold,
    authentication=api_authentication,
)
