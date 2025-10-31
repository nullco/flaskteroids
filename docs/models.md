# Models

Models inherit from `flaskteroids.model.Model` and act as a rich wrapper around your database tables. Database columns are defined during migration and are automatically available as attributes on the model.

The `Model` class provides a powerful API for associations and data validation.

```python
# app/models/post.py
from flaskteroids.model import Model, validates, belongs_to, has_many
from flaskteroids.rules import rules

@rules(
    # --- Associations ---
    belongs_to('user'),
    has_many('comments'),

    # --- Validations ---
    validates('title', presence=True, length={'minimum': 5}),
    validates('content', presence=True)
)
class Post(Model):
    # The database columns (e.g., title, content, user_id) are defined
    # in the database migration and automatically mapped to this model.
    pass
```
