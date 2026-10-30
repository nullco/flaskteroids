# Rate limits

Use a rate limit to reject requests when a client sends too many in a short
period. For example, you can limit repeated requests to a public endpoint.

After reading this guide, you will know how to:

- Add a request limit to a controller.
- Recognize the response when the limit is exceeded.
- Account for process-local counters in a deployment.

## Add a limit

Declare the limit inside the controller class:

```python
from flaskteroids.controller import Controller
from flaskteroids.rate_limit import rate_limit


class StatusController(Controller):
    rate_limit(to=5, within=60)

    def index(self):
        return self.head(200)
```

This allows five requests per client IP within 60 seconds. Exceeding the limit
returns **429 Too Many Requests**. Use `only=["index"]` to apply a limit to
selected actions rather than the whole controller.

To customize the rejection response, pass a controller method name through
`using`, for example `using="_rate_limit_exceeded"`, and return a response
from that method.

## Default cache

Each application has its own counters. **The default cache is in memory and is
not shared between worker processes.** Values disappear when the process ends.

These are not deployment-wide limits. For a multi-process deployment, choose
an appropriate shared rate-limiting solution at your proxy or infrastructure
layer rather than assuming these counters protect all workers together.

## Next steps

See [Controller callbacks](index.md#controller-callbacks) to share other request
checks across actions.
