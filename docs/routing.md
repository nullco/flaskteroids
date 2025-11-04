# Routing

Flaskteroids provides a powerful routing system that allows you to define routes in a clean, RESTful manner. Routes are defined in `config/routes.py` by a `register` function that receives a router instance. You can define standard routes or use resourceful routing to handle RESTful conventions automatically.

## Route Format

Routes map HTTP requests to controller actions using the format `"controller#action"`. Controllers are automatically discovered from the `CONTROLLERS['LOCATION']` directory (default: `app/controllers`), and their class names are derived by camelizing the controller name and appending "Controller" (e.g., `posts` becomes `PostsController`).

## Standard Routes

Standard routes allow you to manually define routes for specific HTTP methods and paths.

### GET Routes

Define a GET route using `router.get(path, to="controller#action", as_=None)`:

```python
# config/routes.py
def register(router):
    router.get("/", to="welcome#index")
    router.get("/about", to="pages#about")
    router.get("/users/:id", to="users#show")
```

### POST Routes

Define a POST route using `router.post(path, to="controller#action", as_=None)`:

```python
def register(router):
    router.post("/users", to="users#create")
    router.post("/login", to="sessions#create")
```

### PUT Routes

Define a PUT route using `router.put(path, to="controller#action", as_=None)`:

```python
def register(router):
    router.put("/users/:id", to="users#update")
```

### DELETE Routes

Define a DELETE route using `router.delete(path, to="controller#action", as_=None)`:

```python
def register(router):
    router.delete("/users/:id", to="users#destroy")
```

### Root Route

The root route maps the home page. If no root route is defined, Flaskteroids automatically adds one pointing to the internal welcome controller.

```python
def register(router):
    router.root(to="welcome#index")  # or router.get("/", to="welcome#index")
```

## Resourceful Routes

Resourceful routing provides automatic generation of RESTful routes for a controller. This follows Rails conventions and eliminates repetitive route definitions.

### Resources (Plural)

The `router.resources(name, param=None, only=None, nested=None)` method generates standard CRUD routes for a plural resource:

```python
def register(router):
    router.resources("posts")
```

This generates the following routes:

| HTTP Method | Path              | Controller#Action | Named Route    |
|-------------|-------------------|-------------------|----------------|
| GET         | /posts/           | posts#index       | index_post     |
| GET         | /posts/new/       | posts#new         | new_post       |
| POST        | /posts/           | posts#create      | create_post    |
| GET         | /posts/:id/       | posts#show        | show_post      |
| GET         | /posts/:id/edit/  | posts#edit        | edit_post      |
| PUT         | /posts/:id/       | posts#update      | update_post    |
| DELETE      | /posts/:id/       | posts#destroy     | destroy_post   |

By default, the `:id` parameter is an integer, but you can customize it:

```python
def register(router):
    router.resources("posts", param="int:post_id")
    # or for string IDs
    router.resources("posts", param="post_id")
```

### Limiting Actions

Use the `only` parameter to generate only specific actions:

```python
def register(router):
    router.resources("posts", only=["index", "show"])
    # Generates only GET /posts/ and GET /posts/:id/
```

### Resource (Singular)

For singular resources (like `/profile`), use `router.resource(name, only=None)`:

```python
def register(router):
    router.resource("profile")
```

This generates:

| HTTP Method | Path              | Controller#Action | Named Route        |
|-------------|-------------------|-------------------|--------------------|
| GET         | /profile/new/     | profiles#new      | new_profile        |
| POST        | /profile/         | profiles#create   | create_profile     |
| GET         | /profile/         | profiles#show     | show_profile       |
| GET         | /profile/edit/    | profiles#edit     | edit_profile       |
| PUT         | /profile/         | profiles#update   | update_profile     |
| DELETE      | /profile/         | profiles#destroy  | destroy_profile    |

Note: The controller name is pluralized (`profiles`), even though the resource is singular.

### Nested Resources

Nest resources to create hierarchical routes:

```python
def register(router):
    router.resources("users", nested=lambda r: [
        r.resources("posts"),
        r.resources("comments")
    ])
```

This generates nested routes like:

- GET /users/:user_id/posts/
- POST /users/:user_id/posts/
- GET /users/:user_id/posts/:id/
- etc.

## Named Routes

All routes automatically receive a generated name, but you can customize it with the `as_` parameter:

```python
def register(router):
    router.get("/dashboard", to="users#dashboard", as_="user_dashboard")
    router.resources("posts", as_="articles")  # Affects all generated routes
```

## JSON Routes

Flaskteroids automatically adds JSON format routes for data-oriented actions:

For resourceful routes, the following JSON routes are added:

- GET /posts/.json/ → posts#index
- POST /posts/.json/ → posts#create
- GET /posts/:id/.json/ → posts#show
- PUT /posts/:id/.json/ → posts#update
- DELETE /posts/:id/.json/ → posts#destroy

## Method Overrides

Since browsers typically only support GET and POST, Flaskteroids provides method override support for PUT and DELETE requests. Include a `_method` parameter in POST requests:

```html
<form action="/posts/1" method="POST">
  <input type="hidden" name="_method" value="PUT">
  <!-- form fields -->
</form>
```

This allows the same URL to handle different HTTP methods based on the `_method` parameter.
