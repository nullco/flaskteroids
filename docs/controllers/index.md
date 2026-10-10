# Controllers

Controllers handle HTTP requests. Each action is a method on a controller class. If an action returns no response, Flaskteroids renders its matching template and passes the controller's instance variables to it.

```python
# app/controllers/posts_controller.py
from flaskteroids import params
from flaskteroids.controller import ActionController
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        # Implicitly renders app/views/posts/index.html and
        # makes self.posts available in the template.

    def show(self):
        self.post = Post.find(params["id"])
        # Implicitly renders app/views/posts/show.html and
        # makes self.post available in the template.
```

## Controller callbacks

Declare `before_action` inside `@rules` to run code before an action. Use it to load records shared by several actions or check authentication:

```python
from flaskteroids import params
from flaskteroids.actions import before_action
from flaskteroids.rules import rules
from flaskteroids.controller import ActionController
from app.models.post import Post

@rules(
    before_action('_set_post', only=['show', 'edit', 'update', 'destroy'])
)
class PostsController(ActionController):
    def show(self):
        # self.post is already set by the callback
        pass

    def _set_post(self):
        self.post = Post.find(params["id"])
```

## Content negotiation

Use `respond` to return HTML or JSON from the same action. It selects a handler based on the request's `Accept` header or a `.json/` URL suffix:

```python
from flaskteroids.controller import ActionController, render, respond
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        return respond(
            html=lambda: render('index'),
            json=lambda: render(json=self.posts)
        )
```
