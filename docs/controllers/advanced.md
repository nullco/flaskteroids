# Rate Limit

You can use the rate_limit rule to restrict how often a particular controller
or action can be called within a given time window.

```python
from cucurbit.controller import ActionController 
from cucurbit.rules import rules
from cucurbit.rate_limit import rate_limit


@rules(
    rate_limit(to=5, within=60),
)
class MyController(ActionController):

    def index(self):
        pass
```
