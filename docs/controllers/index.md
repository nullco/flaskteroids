# Controllers

Controllers handle the logic for incoming requests. Actions are methods within a controller class that set instance variables for the view. Rendering is handled automatically.

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

## Controller Callbacks

You can use callbacks to run code before a controller action. The `before_action` callback is useful for setting up instance variables or performing authentication checks. Callbacks must be defined within a `@rules` decorator.

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

## Content Negotiation

Flaskteroids can handle different response formats within a single action using the `respond_to` block. This is particularly useful for building APIs that serve both HTML and JSON.

```python
from flaskteroids.controller import ActionController, respond_to
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        with respond_to() as format:
            format.html(lambda: render('index'))
            format.json(lambda: render(json=self.posts))
```
