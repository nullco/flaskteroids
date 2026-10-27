"""Select concrete application collaborators once, after configuration."""

from collections.abc import Callable
from dataclasses import dataclass

from flaskteroids._browser import browser_context, install_browser
from flaskteroids._controllers.sessions import StatelessSessionInterface
from flaskteroids._request_policy import (
    API_REQUESTS,
    BROWSER_REQUESTS,
    APIRequestPolicy,
    BrowserRequestPolicy,
)
from flaskteroids._routing import API_ROUTES, BROWSER_ROUTES, RoutingConventions
from flaskteroids.cli.generators.profiles import (
    API_GENERATORS,
    BROWSER_GENERATORS,
    Generators,
)


def _install_stateless_requests(app):
    app.session_interface = StatelessSessionInterface()


def _empty_template_context():
    return {}


@dataclass(frozen=True)
class ApplicationStack:
    facilities: tuple[Callable, ...]
    routing: RoutingConventions
    requests: BrowserRequestPolicy | APIRequestPolicy
    generators: Generators
    template_context: Callable

    def install(self, app):
        for install in self.facilities:
            install(app)


BROWSER_STACK = ApplicationStack(
    facilities=(install_browser,),
    routing=BROWSER_ROUTES,
    requests=BROWSER_REQUESTS,
    generators=BROWSER_GENERATORS,
    template_context=browser_context,
)
API_STACK = ApplicationStack(
    facilities=(_install_stateless_requests,),
    routing=API_ROUTES,
    requests=API_REQUESTS,
    generators=API_GENERATORS,
    template_context=_empty_template_context,
)


def application_stack(config):
    return API_STACK if config.api_only else BROWSER_STACK
