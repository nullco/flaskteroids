# Rate limits

Use the `rate_limit` rule to restrict requests to a controller or action. This example allows five requests within 60 seconds:

```python
from flaskteroids.controller import ActionController
from flaskteroids.rules import rules
from flaskteroids.rate_limit import rate_limit


@rules(
    rate_limit(to=5, within=60),
)
class MyController(ActionController):

    def index(self):
        pass
```
