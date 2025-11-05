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
