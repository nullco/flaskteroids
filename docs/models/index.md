# Models

Flaskteroids models provide a rich, Active Record-inspired API for working with your database. Models inherit from `flaskteroids.model.Model` and act as a wrapper around SQLAlchemy table objects. Database columns defined in migrations are automatically available as attributes on the model instances.

Models support associations, validations, secure password handling, and provide a comprehensive querying interface.

## Defining a Model

Models are defined by inheriting from `Model` and using the `@rules` decorator to apply associations, validations, and other features. The decorators (belongs_to, has_many, validates, etc.) are defined inside the rules decorator.

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
    # Database columns (title, content, user_id, etc.) are automatically available
    pass
```

## Associations

Associations define relationships between models.

### belongs_to

Defines a one-to-one or many-to-one relationship where the model belongs to another model.

```python
from flaskteroids.model import Model, belongs_to
from flaskteroids.rules import rules

@rules(
    belongs_to('user')
)
class Post(Model):
    pass

# Usage
post = Post.find(1)
user = post.user  # Access the associated User
```

You can customize the association:

```python
from flaskteroids.model import Model, belongs_to
from flaskteroids.rules import rules


@rules(
    belongs_to('author', class_name='User', foreign_key='author_id')
)
class Post(Model):
    pass
```

### has_many

Defines a one-to-many relationship where the model has many instances of another model.

```python
from flaskteroids.model import Model, has_many
from flaskteroids.rules import rules

@rules(
    has_many('comments')
)
class Post(Model):
    pass

# Usage
post = Post.find(1)
comments = post.comments  # Returns a Relation object
for comment in comments:
    print(comment.content)

# Create associated records
new_comment = post.comments.create(content="Great post!", author="John")
```

You can customize with `dependent` to handle cascading deletes:

```python
from flaskteroids.model import Model, has_many
from flaskteroids.rules import rules

@rules(
    has_many('comments', dependent='destroy')  # Deletes comments when post is deleted
)
class Post(Model):
    pass
```

## Validations

Validations ensure data integrity before saving records.

### Presence

Ensures a field is not empty.

```python
from flaskteroids.model import Model, validates
from flaskteroids.rules import rules

@rules(
    validates('title', presence=True)
)
class Post(Model):
    pass
```

### Length

Validates the length of a string field.

```python
from flaskteroids.model import Model, validates
from flaskteroids.rules import rules


@rules(
    validates('title', length={'minimum': 5, 'maximum': 100}),
    validates('password', length={'minimum': 8})
)
class Post(Model):
    pass
```

### Confirmation

Validates that two fields match (commonly used for passwords).

```python
from flaskteroids.model import Model, validates
from flaskteroids.rules import rules


@rules(
    validates('password', confirmation=True)
)
class User(Model):
    pass

# Requires both 'password' and 'password_confirmation' fields to match
user = User.new(password="secret", password_confirmation="secret")
```

## Secure Passwords

Adds secure password hashing and authentication methods.

```python
from flaskteroids.model import Model, has_secure_password

@rules(
    has_secure_password()
)
class User(Model):
    pass

# Usage
user = User.create(email="user@example.com", password="secret")
user.authenticate("secret")  # Returns True

# Class methods
User.authenticate_by(email="user@example.com", password="secret")  # Returns user or None
```

The decorator adds:

- Automatic password hashing to `password_digest`
- Virtual fields: `password`, `password_confirmation`, `password_reset_token`
- Validation for password length and confirmation

## Callbacks

Callbacks are hooks that run at specific points in a model's lifecycle,
mirroring Ruby on Rails' Active Record callbacks. They are declared inside the
`@rules` decorator, just like associations and validations.

```python
from flaskteroids.model import Model, before_save, after_create
from flaskteroids.rules import rules

@rules(
    before_save('_normalize_email'),
    after_create('_send_welcome_email'),
)
class User(Model):
    def _normalize_email(self):
        self.email = self.email.strip().lower()

    def _send_welcome_email(self):
        # enqueue a mailer / background job
        pass
```

### Available Callbacks

The full lifecycle is supported, in the same order Rails runs it:

```
before_validation
after_validation
before_save
around_save
  before_create / before_update
  around_create / around_update
  after_create  / after_update
after_save
after_commit / after_rollback
```

For destruction:

```
before_destroy
around_destroy
after_destroy
after_commit
```

Instantiating and loading records also have hooks:

- `after_initialize` — runs when a model is instantiated (`new`, `create`, or loaded from the database).
- `after_find` — runs when a model is loaded from the database (`find`, `find_by`, `all`, and associations).

### Before, Around and After

- **Before** callbacks run before the operation. Returning `False` from a before
  callback halts the chain and aborts the operation (`save()` returns `False`,
  `destroy()` returns `False`).
- **Around** callbacks wrap the operation using a generator. Code before the
  `yield` runs before the operation, and code after the `yield` runs after it.
  An around callback that never yields also halts the chain.
- **After** callbacks run after the operation completes.

```python
@rules(
    before_save('_before'),
    around_save('_around'),
    after_save('_after'),
)
class Post(Model):
    def _before(self):
        pass

    def _around(self):
        # runs before the save
        yield
        # runs after the save

    def _after(self):
        pass
```

Before callbacks run in registration order; after callbacks run in reverse
registration order (LIFO), matching Rails.

### Conditional Callbacks

Use `if_` and `unless_` to control when a callback runs. Each accepts a method
name (a string) or a callable that receives the model instance.

```python
@rules(
    before_save('_normalize_email', if_='_email_present'),
    before_save('_log_change', unless_=lambda user: user.admin),
)
class User(Model):
    def _email_present(self):
        return bool(self.email)
```

Use `on=` to restrict a callback to `'create'` or `'update'` (and `'destroy'`
for `after_commit`/`after_rollback`). It is only available on validation, save,
commit, and rollback callbacks:

```python
@rules(
    before_validation('_generate_slug', on='create'),
    after_commit('_broadcast', on=['create', 'update']),
)
class Post(Model):
    pass
```

### Ordering with `prepend`

By default callbacks are appended to the chain. Pass `prepend=True` to insert a
callback at the front of the chain:

```python
@rules(
    before_save('_first'),
    before_save('_second', prepend=True),  # runs before _first
)
class Post(Model):
    pass
```

### After Commit and After Rollback

`after_commit` and `after_rollback` run once the surrounding database
transaction is committed or rolled back — useful for side effects that should
only happen after the data is durably saved (e.g., sending emails, purging a
cache). They support the `on=` option (`'create'`, `'update'`, or `'destroy'`).

```python
@rules(
    after_commit('_purge_cache'),
)
class Post(Model):
    def _purge_cache(self):
        pass
```

## Querying Models

Models provide a rich querying interface through the `ModelQuery` class.

### Finding Records

```python
# Find by ID
post = Post.find(1)

# Find first by criteria
post = Post.find_by(title="Hello World")

# Get all records
posts = list(Post.all())
```

### Where Clauses

```python
# Simple where
posts = Post.where(published=True)

# Multiple conditions
posts = Post.where(published=True).where(user_id=1)

# Using expressions
from sqlalchemy import or_
posts = Post.where(or_(Post.title.like("%hello%"), Post.content.like("%world%")))
```

### Includes (Eager Loading)

Load associated records to avoid N+1 queries.

```python
# Eager load associations
posts = Post.includes('user', 'comments').all()

for post in posts:
    print(post.user.name)  # No additional query
    for comment in post.comments:
        print(comment.content)  # No additional query
```

### Ordering

```python
# Order by created_at descending
posts = Post.order(created_at='desc').all()

# Multiple order clauses
posts = Post.order(created_at='desc', title='asc').all()
```

## CRUD Operations

### Creating Records

```python
# Create and save immediately
post = Post.create(title="New Post", content="Content here")

# Create without saving
post = Post.new(title="New Post", content="Content here")
post.save()  # Returns True on success
```

### Updating Records

```python
post = Post.find(1)
post.title = "Updated Title"
post.save()

# Or update multiple fields at once
post.update(title="New Title", content="New Content")
```

### Deleting Records

```python
post = Post.find(1)
post.destroy()
```

## Error Handling

Models include an `errors` object for validation errors.

```python
post = Post.new(title="")  # Invalid: title is required
post.save()  # Returns False

if post.errors:
    print("Errors:", post.errors.full_messages())

# Errors are automatically cleared on successful save
```

## Authentication

For models with secure passwords:

```python
# Authenticate a user
user = User.authenticate_by(email="user@example.com", password="secret")

# Password reset tokens
token = user.password_reset_token
# Later...
user = User.find_by_password_reset_token(token)
```
