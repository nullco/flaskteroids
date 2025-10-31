# Routing

Routes are defined in `config/routes.py` by a `register` function that receives a router instance. You can define standard routes or use resourceful routing to handle RESTful conventions automatically.

```python
# config/routes.py
def register(router):
    # A standard route
    router.get("/", to="welcome#index")

    # Resourceful routes for a 'posts' controller
    router.resources("posts")
```
