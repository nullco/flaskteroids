# Application middleware

Middleware wraps the whole application before routing and controller callbacks.
Use it for concerns that apply to every request, such as adding a response
header or handling a trusted reverse proxy.

After reading this guide, you will know how to:

- Write and register WSGI middleware.
- Change its place in the request stack.
- Inspect the stack used by your application.

Use [controller callbacks](../controllers/index.md#controller-callbacks) instead
when the behavior needs controller state or a browser session.

## Write and register middleware

Create `app/middleware/security_headers.py`:

```python
class SecurityHeaders:
    def __init__(self, app, *, policy="nosniff"):
        self.app = app
        self.policy = policy

    def __call__(self, environ, start_response):
        def secured_response(status, headers, exc_info=None):
            headers = [*headers, ("X-Content-Type-Options", self.policy)]
            return start_response(status, headers, exc_info)

        return self.app(environ, secured_response)
```

Register it in `config/application.py`:

```python
from app.middleware.security_headers import SecurityHeaders
from flaskteroids.application import Application as FlaskteroidsApplication
from config.boot import ROOT


class Application(FlaskteroidsApplication):
    root = ROOT

    def configure(self, config):
        config.load_defaults("0.1")
        config.middleware.use(SecurityHeaders, policy="nosniff")
```

The constructor receives the next WSGI application and your configured arguments.
Its `__call__` method delegates the request and adds a response header.

Middleware instances are shared across requests. Keep request-specific state in
local variables or `environ`, not instance attributes. Middleware does not
automatically have a Flask request or application context.

Delegate the response body unchanged unless you need to transform it. If you
wrap the body, preserve its `close()` cleanup. Exceptions outside Flask dispatch
are not handled by Flask error handlers.

## Configure the stack

The default incoming-request order is:

1. Werkzeug's `ProxyFix`.
2. `MethodOverrideMiddleware` in browser applications.
3. Flask dispatch.

`use()` adds middleware just before Flask dispatch. Requests travel down the
stack; response calls unwind in reverse. For a specific position, register your
middleware relative to a class already in the stack:

```python
from werkzeug.middleware.proxy_fix import ProxyFix

from app.middleware.security_headers import SecurityHeaders

# Inside configure:
config.middleware.insert_after(ProxyFix, SecurityHeaders)
```

Use `config.middleware.delete(SecurityHeaders)` to remove it. Supply classes,
not class-name strings. A missing insertion target fails at startup; deleting
a missing target is harmless.

Environment configuration can also change `config.middleware`. The final stack
is built after initializers; restart the application after changing it.

### Trusted proxies

Only trust forwarding headers when requests pass through the corresponding
trusted proxies. Configure `ProxyFix` hop counts for your deployment:

```python
from werkzeug.middleware.proxy_fix import ProxyFix

# Inside configure; this example assumes one trusted proxy:
config.middleware.swap(ProxyFix, ProxyFix, x_for=1, x_proto=1)
```

Remove `ProxyFix` if proxy handling is not appropriate. See the
[Werkzeug ProxyFix documentation](https://werkzeug.palletsprojects.com/en/stable/middleware/proxy_fix/)
before choosing these values.

Removing `MethodOverrideMiddleware` disables browser form method overrides.
API-only applications do not include it by default.

## Inspect the stack

From your application root, run:

```sh
bin/flask middleware
```

The command loads the application and lists middleware in incoming-request order,
followed by Flask dispatch.

## Next steps

See [Configuration](../configuration.md) for environment settings, or
[Routing](../controllers/routing.md) to follow a request into a controller.
