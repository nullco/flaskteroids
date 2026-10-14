# Models

Models inherit from `flaskteroids.model.Model` and wrap SQLAlchemy table objects with an Active Record-style API. Database columns defined in migrations become attributes on model instances.

Use models to query records, define associations and validations, and handle passwords.

## Define a model

Inherit from `Model` and declare associations and validations inside `@rules`:

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

## Custom rules and inheritance

A custom rule receives a class. Use it to set class attributes. Put database
queries and other work that needs an application in an action, callback, or
initializer instead.

```python
def searchable(*names):
    def prepare(cls):
        cls.search_fields = names
    return prepare


@rules(searchable('title'))
class Post(Model):
    pass
```

Rules run once for each class. Inherited rules run before the child's rules, in
base-class order. A shared ancestor contributes its rules once. Declaring the
same rule twice runs it twice. If a rule uses a list or dictionary, create a new
one for each class so children do not change their parents' values.

## Temporary attributes

Unknown attributes raise `AttributeError`, helping you catch typos. This applies
to both direct assignment and values passed to `new()`, `create()`, or `update()`.

For values you don't want to save, declare a class default or use a private name:

```python
class Post(Model):
    delivery_hint = None


post = Post.new(title="Draft", delivery_hint="preview")
post._render_cache = {}
# post.titel = "Typo" raises AttributeError
```

Inherited defaults and properties with setters work too. A type annotation alone
isn't enough. Read-only attributes and framework methods cannot be overwritten.

Temporary values aren't saved or included in automatic JSON or form data.
They survive `reload()` on the same instance; separately loaded instances start
with class defaults. Initialize lists and dictionaries per instance, not as
shared class defaults.

## Associations

Associations define relationships between models.

### belongs_to

Use `belongs_to` when the model holds a foreign key to another model. For example, a post belongs to a user:

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

Set `post.user` to a `User` instance, or `None` to clear it, then call
`post.save()`. Save new users first. A wrong model type raises `TypeError`;
clearing a required association makes `save()` return `False`.

### has_many

Use `has_many` for a one-to-many relationship. For example, a post has many comments:

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

Collections support iteration and `create()`, not `append()` or `remove()`.
Replacing a collection with `post.comments = []` raises `AttributeError`.

Set `dependent='destroy'` to delete associated records when you destroy the parent:

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

Validations check model attributes before saving. A failed validation prevents the save and adds messages to the model's `errors` object.

### Presence

Reject empty values:

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

Require a field to match its confirmation field, usually for passwords:

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

## Password hashing

Use `has_secure_password()` to hash passwords and `PasswordAuthenticator` for authentication methods. The database table needs a `password_digest` column.

```python
from flaskteroids.model import Model, PasswordAuthenticator, has_secure_password
from flaskteroids.rules import rules

@rules(
    has_secure_password()
)
class User(Model, PasswordAuthenticator):
    pass

# Usage
user = User.create(email="user@example.com", password="secret")
user.authenticate("secret")  # Returns True

# Class methods
User.authenticate_by(email="user@example.com", password="secret")  # Returns user or None
```

The rule and authenticator provide:

- Automatic password hashing to `password_digest`
- Virtual fields: `password`, `password_confirmation`, `password_reset_token`
- Validation for password length and confirmation
- Password reset tokens that expire after 15 minutes and become invalid after a
  successful password change

## JSON serialization

`render(json=record)` and `render(json=Model.all())` serialize database columns,
including pending column changes. They omit `password`, `password_confirmation`,
`password_digest`, and `password_reset_token`. The corresponding attributes for
custom `has_secure_password()` field names are omitted too.

Virtual fields and associations are not included automatically. Serialization
does not generate reset tokens or evaluate read-only virtual fields. Read
`user.password_reset_token` explicitly when issuing a password reset.

To select fewer columns or add an application-specific value, override the existing
`__json__()` protocol. Queries use the same override for each record:

```python
class User(Model):
    def __json__(self):
        data = super().__json__()
        return {"id": data["id"], "name": data["name"]}
```

All other database columns are included by default. Filter application-specific
secrets in your override, and do not add authentication fields back to the result.
`form_with(model=record)` extracts form values independently of `__json__()`.
Changing response serialization does not change model-backed form values.

Applications upgrading from the previous behavior must explicitly select any
virtual fields they intend to publish. Passwords, digests, and reset tokens must
not be published through ordinary record responses.

## Callbacks

Callbacks run at specific points in a model's lifecycle. Declare them inside `@rules`, alongside associations and validations.

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

### Available callbacks

Save callbacks run in this order:

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

Two callbacks run when you instantiate or load records:

- `after_initialize` runs when you instantiate a model with `new` or `create`, or load it from the database.
- `after_find` runs when you load a model through `find`, `find_by`, `all`, or an association.

### Before, around, and after

Before callbacks run before the operation. Returning `False` halts the chain and aborts the operation. In that case, `save()` or `destroy()` returns `False`.

Around callbacks wrap the operation using a generator. Code before `yield` runs before the operation. Code after `yield` runs after it. An around callback that never yields also halts the chain.

After callbacks run when the operation completes.

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

Before callbacks run in registration order. After callbacks run in reverse registration order.

### Conditional callbacks

Use `if_` and `unless_` to control when a callback runs. Each accepts a method name as a string, or a callable that receives the model instance.

```python
@rules(
    before_save('_normalize_email', if_='_email_present'),
    before_save('_log_change', unless_=lambda user: user.admin),
)
class User(Model):
    def _email_present(self):
        return bool(self.email)
```

Use `on=` to restrict a callback to `'create'` or `'update'`. Commit and rollback callbacks also accept `'destroy'`. The option is available only on validation, save, commit, and rollback callbacks:

```python
@rules(
    before_validation('_generate_slug', on='create'),
    after_commit('_broadcast', on=['create', 'update']),
)
class Post(Model):
    pass
```

### Ordering with `prepend`

By default, Flaskteroids adds callbacks to the end of the chain. Pass `prepend=True` to insert a callback at the front:

```python
@rules(
    before_save('_first'),
    before_save('_second', prepend=True),  # runs before _first
)
class Post(Model):
    pass
```

### After commit and after rollback

`after_commit` runs once the surrounding database transaction commits. Use it for work that must wait until the data is saved, such as sending an email or purging a cache. `after_rollback` runs once the transaction rolls back. Both accept `on='create'`, `on='update'`, or `on='destroy'`.

```python
@rules(
    after_commit('_purge_cache'),
)
class Post(Model):
    def _purge_cache(self):
        pass
```

## Querying models

Start a query with `where`, `order`, or `all`. These methods return a `ModelQuery` that you can chain to filter, order, or paginate records.

### Finding records

```python
# Find by ID
post = Post.find(1)

# Find first by criteria
post = Post.find_by(title="Hello World")

# Get all records
posts = list(Post.all())
```

### Where clauses

```python
# Simple where
posts = Post.where(published=True)

# Multiple conditions
posts = Post.where(published=True).where(user_id=1)

# Using expressions
from sqlalchemy import or_
posts = Post.where(or_(Post.title.like("%hello%"), Post.content.like("%world%")))
```

### Eager loading with `includes`

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

### Limit, offset, and pagination

Use `limit()` to cap the number of records and `offset()` to skip records. Both
methods work directly on a model or in a query chain and are applied in SQL:

```python
posts = Post.limit(10)
posts = Post.offset(20)
posts = Post.where(published=True).order(id='asc').limit(10).offset(20)

# Page numbers start at 1
page = 3
per_page = 20
posts = Post.where(published=True).order(id='asc').limit(per_page).offset((page - 1) * per_page)
records = list(posts)

# Count all matching records separately from the page
page_count = posts.count()
total_count = Post.where(published=True).count()
```

Always use a deterministic order, such as `id`, for pagination. Limits and offsets must be non-negative integers. `limit(0)` returns no records, and `offset(0)` skips none.

Repeated calls replace the previous value. `limit(None)` or `offset(None)` clears that clause. Queries execute when you request records or a count.

`count()`, `first()`, and `last()` respect the selected page. `last()` loads the selected records when a limit or offset is present.

## CRUD operations

### Creating records

```python
# Create and save immediately
post = Post.create(title="New Post", content="Content here")

# Create without saving
post = Post.new(title="New Post", content="Content here")
post.save()  # Returns True on success
```

### Updating records

```python
post = Post.find(1)
post.title = "Updated Title"
post.save()

# Or update multiple fields at once
post.update(title="New Title", content="New Content")
```

If `update()` encounters an unknown attribute, it raises without saving. Earlier
valid assignments from that call aren't undone.

### Null attributes

Column assignments preserve `None` for every supported field type. An explicit
`record.update(name=None)` requests clearing that attribute; omitting `name` from
an update leaves its existing value unchanged. Direct assignment and `new()` use
the same casting rules. See [Fields](../other/fields.md#null-values) for JSON
storage details.

Null values still undergo validation and database constraints. For example,
`Post.new(title=None)` fails `save()` when `title` has presence validation, just
like an omitted title. A rejected update retains the pending null in memory but
does not save it; use `reload()` to restore persisted values. Saving SQL `NULL`
to a non-nullable column without applicable validation still raises a database
integrity error.

Applications upgrading from older casting behavior must assign `False`
explicitly when they mean false, rather than using `None`. Previously saved
`"None"` strings and false values are not automatically rewritten.

### Deleting records

```python
post = Post.find(1)
post.destroy()
```

## Missing tables

If a model's table doesn't exist yet, the app can still start, but using that
model raises `ProgrammerError`. Run `flask db:migrate`, then restart the app.

Other setup errors, such as an invalid association or a table without a primary
key, must be fixed before the app can start.

## Validation errors

Models include an `errors` object for validation errors. `render(json=record.errors,
status=422)` returns a JSON list of full messages, or `[]` when there are no errors.

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
# Within 15 minutes, before the password changes
user = User.find_by_password_reset_token(token)
```

Reset tokens are signed and scoped to the model and password field. They contain a
keyed fingerprint of the password digest, not the digest itself. Any successful
password change invalidates all outstanding reset tokens, even when setting the
same password again. Failed password updates and changes to unrelated fields do
not invalidate existing tokens.

Reading `password_reset_token` generates a fresh token using the current password
digest and timestamp. For custom password fields, such as `has_secure_password('passcode')`,
read `passcode_reset_token`; verification still uses `find_by_password_reset_token()`.

Verification raises `itsdangerous.SignatureExpired` for expired tokens and
`itsdangerous.BadSignature` for invalid or revoked tokens. Previously issued tokens
from versions without expiration and password-change protection are rejected;
users must request a new reset link.
