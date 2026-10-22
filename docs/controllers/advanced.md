# Rate limits

Use the `rate_limit` declaration to restrict requests to a controller or action. This example allows five requests within 60 seconds:

```python
from flaskteroids.controller import ActionController
from flaskteroids.rate_limit import rate_limit


class MyController(ActionController):
    rate_limit(to=5, within=60)

    def index(self):
        pass
```

Limits count requests by client IP by default. Each application has separate
counters.

## Default cache

Use `flaskteroids.cache.store(key, value, ttl=seconds)`, `fetch(key)`, and
`increment(key, ttl=seconds)`. `fetch` returns `cache.MISSING` for missing or
expired entries. Incrementing resets the expiry time.

The default cache stores values in memory, separately for each application.
Calls outside an application context use a separate cache. Values are not shared
between worker processes.
