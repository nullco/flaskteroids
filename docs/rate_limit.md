# Rate Limit

You can use the rate_limit rule to restrict how often a particular controller
or action can be called within a given time window.

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
