# Models

Flaskteroids models are SQLAlchemy-mapped application objects with Rails-like
querying, validation, and persistence methods. Columns come from a generated
snapshot of the migrated database; behavior and association rules stay in model
files. There is no separate mapped row hidden behind a model.

## Define models and migrate

All application models inherit an abstract application base:

```python
# app/models/application_model.py
from flaskteroids.model import Model

class ApplicationModel(Model):
    __abstract__ = True
```

```python
# app/models/author.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_many, validates
from flaskteroids.rules import rules

@rules(has_many("posts", dependent="destroy"), validates("name", presence=True))
class Author(ApplicationModel):
    def greeting(self):
        return f"Hello, {self.name}"
```

```python
# app/models/post.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to, validates
from flaskteroids.rules import rules

@rules(belongs_to("author"), validates("title", presence=True))
class Post(ApplicationModel):
    pass
```

Create the tables through migrations:

```sh
flask generate model Author name:string
flask generate model Post title:string author:references
flask db:prepare
```

Model/scaffold generators write migrations and behavioral model files. Successful
`db:migrate`, `db:prepare`, and `db:rollback` regenerate `app/schema.py` from the
selected database. Commit it, but **do not edit it manually**. Use
`flask db:schema:dump` to refresh it independently. See [CLI](../other/cli.md).

The snapshot contains metadata for tables, columns, keys, constraints, indexes,
and server defaults, including tables without a behavioral model. It contains no
model behavior, validators, or relationship choices. `Post` conventionally maps
to `posts`; a model may set `__table_name__ = "legacy_posts"` for another table.

## Lazy mapping and normal startup

Importing a model only declares its behavior and collects its `@rules`. It does
not require a snapshot or connect to the database. Mapping happens when needed:
constructing a record, using the query facade, or accessing a mapped expression
such as `Post.title`.

Consequently, ordinary application startup and migration commands work before a
new model has a table in the snapshot. They use the same initialization path;
initializers are not skipped. An initializer that actually uses an unavailable
model still fails with migration guidance.

The mapper reads the snapshot, not the live database. Restart servers and workers
after migration. Do not reload schema files or alter published mappings in place.
Abstract behavior bases need no table. Concrete model inheritance, duplicate model
names within an application model set, and columns that shadow model APIs are
rejected. Different model sets have isolated registries; matching schemas can use
the same mapped classes with separate engines/sessions.

## Queries

```python
post = Post.find(1)                      # Raises RecordNotFoundException if absent
post = Post.find_by(title="First")       # Returns None if absent
posts = Post.where(title="First").all()  # A list of mapped Post objects
posts = Post.where(Post.title.ilike("a%"))
page = posts.order(title="asc").limit(20).offset(40)
count = page.count()
first = page.first()
last = page.last()
```

Queries are lazy and **immutable**. Chain or assign the returned query; a call to
`query.where(...)` does not change the original query. Queries are reusable and
iterable. Default ordering is ascending primary key; `order()` also accepts native
SQLAlchemy ordering expressions. Limits and offsets must be nonnegative or `None`.
`count()` respects the selected scope/page. `first()` returns one record or `None`;
`last()` materializes the selected scope to honor custom ordering and pagination.

Use eager loading to avoid per-row relationship queries:

```python
posts = Post.includes("author").all()
authors = Author.includes("posts.author").all()
```

`includes()` accepts dotted relationship paths and uses native select-in loaders.
Unknown relationships raise `AttributeError`; malformed paths raise `ValueError`.
For complex queries, use `query.statement`, `query.options(...)`, or native SQLAlchemy.

## Assignment, validation, and persistence

```python
post = Post.new(title="First", author=author)
if post.save():
    identifier = post.id
else:
    messages = post.errors.full_messages()

post = Post.create(title="", author=author)  # Returns the invalid, unsaved object
assert post.errors
assert post.update(title="Fixed")
```

Scalar assignments are staged on the mapped object. Reads expose entered values,
but SQLAlchemy's published state is unchanged until a successful save. Invalid
updates retain their input/errors without being flushed by another object's save
or the context's final commit. This also applies to valid edits never explicitly
saved, and to edits made after an earlier save.

`save()` validates and flushes; it does **not** commit. `save(validate=False)` is an
explicit validation bypass. Database constraints remain authoritative: integrity
errors propagate rather than becoming validation errors. If you catch a database
or unexpected callback exception, roll back/recover the transaction before further
writes. A handled validation failure returning `False` does not itself roll back
other successful writes.

```python
@rules(
    validates("title", presence=True, length={"minimum": 3, "maximum": 100}),
    validates("quantity", numericality={"only_integer": True}),
    validates("quantity", comparison={"greater_than_or_equal_to": 0}),
    validates("email", confirmation=True),
)
class Product(ApplicationModel):
    pass
```

`confirmation=True` makes a writable confirmation field available. Validators run
in declaration order. `errors` is truthy when populated and exposes `count`,
`full_messages()`, and JSON full-message lists. `is_valid()` runs validation without
publishing input. Types/casting do not replace explicit user-facing validation.

Model assignment casts supported scalar types and retains original input through
`read_attribute_before_type_cast(name)` and `attributes_before_type_cast`.
Numericality checks raw input rather than trusting a permissive numeric cast.
Model-backed forms redisplay that input after failed validation; see
[Fields](../other/fields.md) and [Forms](../other/forms.md).

`reload()` refreshes published state and discards staged scalar input/errors.
`discard_changes()` only discards staged scalars. Native refresh/expiration does
not by itself clear the staging dictionary.

### Defaults

Put persistent defaults in migrations. Simple SQL literal server defaults are
available on new objects without querying the database. SQL functions, computed
columns, and generated identities remain server-owned and populate on flush.
Explicit `None` is not mistaken for a request to reuse a server default; JSON
retains its native JSON-null behavior. As a framework convention, `save()` maintains
declared `created_at`/`updated_at` attributes itself; native writes do not implicitly
run that timestamp lifecycle.

Python default functions are not recoverable from a database snapshot. Implement
application-side defaults explicitly in behavior/callbacks, rather than writing
`Column.default` definitions or editing the generated snapshot.

## Association decorators

Keep association declarations inside `@rules`:

```python
@rules(
    belongs_to("author", class_name="User", foreign_key="author_id"),
    has_many("comments", dependent="destroy"),
    has_one("preview", class_name="Preview", foreign_key="post_id"),
)
class Post(ApplicationModel):
    pass
```

The helpers translate into SQLAlchemy relationships before mapping. Class names
and foreign keys are inferred conventionally; the shown positional/keyword options
remain available. `belongs_to()` requires its target by default; use
`optional=True` when absence is allowed. `inverse_of="posts"` selects an explicit
inverse when conventions would be ambiguous. The helpers require single-column
primary keys; use native relationships for more complex joins.

```python
post.author = author
assert post in author.posts
post.save()

post = Post.create(title="Next", author=author)
```

Collections are native SQLAlchemy collections, not custom `Relation` wrappers.
They support assignment, append/remove, iteration, and native loader behavior.
Create a record with `Post.create(author=author, ...)`, not `author.posts.create()`.
Related new framework objects are validated before their staged scalars are
published by a framework save.

Relationship mutations are **not scalar staging**: they have native unit-of-work
semantics. A failed scalar validation does not undo a prior collection edit. When
abandoning an invalid transient child, remove it from the collection; do not leave
an unpublished new object pending in the session. For coherent inverse updates,
assign the relationship itself; raw foreign-key edits may require reloading cached
relationships, just as with native SQLAlchemy.

### Deletion

`record.destroy()` runs framework destroy callbacks and flushes deletion without
committing. `dependent="destroy"` calls related records' framework `destroy()`
methods, including their callbacks and attachment cleanup. A halted destroy
returns `False`; callers needing multi-record atomicity should explicitly own the
transaction and roll it back on rejection.

Native `session.delete()` and ORM/database cascades do not automatically run
framework child `destroy()` callbacks. Native `relationship()` options are an
escape hatch, but must not be confused with the helper's callback-aware contract.
Database `ON DELETE` choices belong in migrations.

## Native SQLAlchemy and transactions

```python
from sqlalchemy import inspect, select
from sqlalchemy.orm import selectinload
from flaskteroids.db import session

Author.prepare()  # Explicit, database-free mapping for bare native class APIs
mapper = inspect(Author)
author = session.get(Author, 1)
authors = session.scalars(select(Author).options(selectinload(Author.posts))).all()
assert Author.find(author.id) is author
```

Facade and native queries return the same objects within a session. Mapped columns
and relationships are real SQLAlchemy attributes. Staged scalar values are the
intentional boundary: SQLAlchemy history and SQL predicates describe published
state, not `record.changes`. `read_published_attribute(name)` bypasses staged input.

Native callers can explicitly publish without validation or framework callbacks:

```python
post = Post(title="Native", author=author).apply_changes()
session.add(post)
session.flush()
```

Directly adding a new record with unpublished staged input is rejected at flush,
rather than silently inserting null/default data. Native/bulk operations bypass
framework validations and operation callbacks. In-place mutable values follow
native SQLAlchemy tracking; use scalar reassignment when you want staged edits.

Sessions are app-context-local, with autoflush disabled and committed attributes
retained. Normal context teardown commits; an escaping exception rolls back;
both paths close the session. A handled HTTP error response alone does not imply
rollback. Use explicit transaction blocks for multi-record operations and native
work that must succeed or fail together. Caller-created sessions are caller-owned.

## Callbacks and authentication

Declare callbacks through `@rules(before_validation(...), before_save(...), ...)`.
Supported operation callbacks include before/after validation; before/around/after
save, create, update, and destroy; after initialize/find; and after commit/rollback.
Around callbacks are generators that yield once. Before callbacks returning
`False` halt their operation. Callback bodies can update staged scalar attributes.

Load callbacks run when an object is actually hydrated, not on every query that
returns an already-loaded identity. After-find runs before after-initialize on
hydration. Commit/rollback callbacks are queued by successful framework operations
and are transaction-scoped; after-commit runs only after the outer commit, not a
flush/savepoint. Native and bulk writes do not imply these framework hooks.

Use `PasswordAuthenticator` and `@rules(has_secure_password())` for password
behavior; a custom field name such as `has_secure_password("passcode")` is supported.
Authentication/reset-token checks use published digests, so a failed staged password
edit does not invalidate persisted credentials. Passwords, digests, confirmations,
and reset tokens are excluded from default JSON/form data. Explicit raw-input APIs
remain sensitive; do not log them. Attachments retain their post-commit upload and
rollback semantics; see [Attachments](../other/attachments.md).

## Temporary attributes and serialization

Unknown public assignments raise `AttributeError`. Declare a class default or a
property with a setter for transient values, or use a private cache name. Initialize
mutable caches per instance. Transients are not automatically saved or serialized;
ordinary identity-map lookups return the same instance and its transient state.
Framework methods and metadata cannot be replaced through assignment.

Default JSON contains mapped scalar attributes, including staged values, excluding
authentication secrets and virtual fields. Override `__json__()` to define an
application-specific response, or add names to `_serialization_exclude` as a set.
Forms obtain values independently of that response representation. Dynamic mapped
fields are not generally inferred by ordinary Python editors/type checkers.
