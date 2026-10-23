# Rate limits

Use a rate limit to reject requests when a client sends too many in a short
period. This example allows five requests per client IP within 60 seconds:

```python
from flaskteroids.controller import ActionController
from flaskteroids.rate_limit import rate_limit


class MyController(ActionController):
    rate_limit(to=5, within=60)

    def index(self):
        pass
```

Declare the limit inside the controller class. Limits count by client IP unless
you configure another key. Exceeding a limit returns **429 Too Many Requests**.
Pass `with_="_rate_limit_exceeded"` to use a controller method as the handler.

Each application has its own counters. **The default cache is in memory and is
not shared between worker processes**, so these are not deployment-wide limits.
Account for that boundary when using them to protect a multi-process application.

## Default cache

Rate limits use the framework cache. You can also use it directly through
`flaskteroids.cache`:

| Operation | API |
| --- | --- |
| Store a value with an expiry | `cache.store(key, value, ttl=seconds)` |
| Read a value | `cache.fetch(key)` |
| Increment a counter and reset its expiry | `cache.increment(key, ttl=seconds)` |

`fetch` returns `cache.MISSING` for a missing or expired entry.

Cache values are separate for each application. Calls outside an application
context use another cache. Values are not shared across processes and are lost
when the process ends.
