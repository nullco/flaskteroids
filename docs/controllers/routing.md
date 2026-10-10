# Routing

Define routes in `config/routes.py`. Its `register` function receives a router instance. You can map individual HTTP methods and paths, or use `resources` to generate CRUD routes.

## Route format

Routes map requests to controller actions using `"controller#action"`. Flaskteroids discovers controllers in the `CONTROLLERS['LOCATION']` directory, which defaults to `app/controllers`. It converts controller names to CamelCase and appends `Controller`. For example, `posts#show` calls `PostsController.show`.

## Standard routes

Map an HTTP method and path to an action:

### GET routes

Define a GET route using `router.get(path, to="controller#action", as_=None)`:

```python
# config/routes.py
def register(router):
    router.get("/", to="welcome#index")
    router.get("/about", to="pages#about")
    router.get("/users/<int:id>", to="users#show")
```

### POST routes

Define a POST route using `router.post(path, to="controller#action", as_=None)`:

```python
def register(router):
    router.post("/users", to="users#create")
    router.post("/login", to="sessions#create")
```

### PUT routes

Define a PUT route using `router.put(path, to="controller#action", as_=None)`:

```python
def register(router):
    router.put("/users/<int:id>", to="users#update")
```

### PATCH routes

Define a PATCH route using `router.patch(path, to="controller#action", as_=None)`:

```python
def register(router):
    router.patch("/users/<int:id>", to="users#update")
```

Resource update routes accept both PUT and PATCH.

### DELETE routes

Define a DELETE route using `router.delete(path, to="controller#action", as_=None)`:

```python
def register(router):
    router.delete("/users/<int:id>", to="users#destroy")
```

### Root route

The root route maps `/`. If you do not define one, Flaskteroids adds a route to its welcome controller.

```python
def register(router):
    router.root(to="welcome#index")  # or router.get("/", to="welcome#index")
```

## Resource routes

Use `resources` to generate the standard CRUD routes for a controller.

### Plural resources

The `router.resources(name, param=None, only=None, nested=None)` method generates standard CRUD routes for a plural resource:

```python
def register(router):
    router.resources("posts")
```

This generates the following routes:

| HTTP method | Path                   | Controller#Action | Named route    |
|-------------|------------------------|-------------------|----------------|
| GET         | /posts/                | posts#index       | index_post     |
| GET         | /posts/new/            | posts#new         | new_post       |
| POST        | /posts/                | posts#create      | create_post    |
| GET         | /posts/<int:id>/       | posts#show        | show_post      |
| GET         | /posts/<int:id>/edit/  | posts#edit        | edit_post      |
| PUT/PATCH   | /posts/<int:id>/       | posts#update      | update_post    |
| DELETE      | /posts/<int:id>/       | posts#destroy     | destroy_post   |

The identifier defaults to `<int:id>`. Use `param` to change its name or type:

```python
def register(router):
    router.resources("posts", param="int:post_id")
    # or for string IDs
    router.resources("posts", param="post_id")
```

### Limiting actions

Use the `only` parameter to generate only specific actions:

```python
def register(router):
    router.resources("posts", only=["index", "show"])
    # Generates only GET /posts/ and GET /posts/<int:id>/
```

### Singular resources

For a resource without an identifier in its path, such as `/profile`, use `router.resource(name, only=None)`:

```python
def register(router):
    router.resource("profile")
```

This generates:

| HTTP method | Path              | Controller#Action | Named route        |
|-------------|-------------------|-------------------|--------------------|
| GET         | /profile/new/     | profiles#new      | new_profile        |
| POST        | /profile/         | profiles#create   | create_profile     |
| GET         | /profile/         | profiles#show     | show_profile       |
| GET         | /profile/edit/    | profiles#edit     | edit_profile       |
| PUT/PATCH   | /profile/         | profiles#update   | update_profile     |
| DELETE      | /profile/         | profiles#destroy  | destroy_profile    |

The controller name is still plural, so `profile` routes to `ProfilesController`.

### Nested resources

Nest resources to create hierarchical routes:

```python
def register(router):
    router.resources("users", nested=lambda r: [
        *r.resources("posts"),
        *r.resources("comments")
    ])
```

The generated paths include:

- `GET /users/<int:user_id>/posts/`
- `POST /users/<int:user_id>/posts/`
- `GET /users/<int:user_id>/posts/<int:id>/`

## Named routes

Flaskteroids generates a name for each route. Use `as_` to override it:

```python
def register(router):
    router.get("/dashboard", to="users#dashboard", as_="user_dashboard")
    router.resources("posts", as_="articles")  # Affects all generated routes
```

### Path and URL helpers

Resource routes generate path and URL helpers:

```python
from flaskteroids.routes import (
    edit_post_path,
    new_post_path,
    post_path,
    post_url,
    posts_path,
)

posts_path()             # /posts/
new_post_path()          # /posts/new/
post_path(post)          # /posts/1/
edit_post_path(post)     # /posts/1/edit/
post_url(post)           # http://example.test/posts/1/
```

Helpers accept either a model instance or an identifier.

## JSON routes

Resource routes also include `.json/` paths for `index`, `create`, `show`, `update`, and `destroy`:

| HTTP method | Path | Action |
| --- | --- | --- |
| GET | `/posts/.json/` | `posts#index` |
| POST | `/posts/.json/` | `posts#create` |
| GET | `/posts/<int:id>/.json/` | `posts#show` |
| PUT/PATCH | `/posts/<int:id>/.json/` | `posts#update` |
| DELETE | `/posts/<int:id>/.json/` | `posts#destroy` |

## Method overrides

HTML forms support GET and POST. To submit a PUT or DELETE request, include a `_method` parameter in a POST form:

```html
<form action="/posts/1" method="POST">
  <input type="hidden" name="_method" value="PUT">
  <!-- form fields -->
</form>
```

Flaskteroids dispatches the request using the `_method` value rather than POST. Include a CSRF token as described in [Forms](../other/forms.md).
