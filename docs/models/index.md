# Models

Flaskteroids models are SQLAlchemy-mapped application objects with Rails-like
querying, validation, and persistence methods. Columns come from a generated
snapshot of the migrated database; behavior and association declarations stay in model
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


class Author(ApplicationModel):
    has_many("posts", dependent="destroy")
    validates("name", presence=True)

    def greeting(self):
        return f"Hello, {self.name}"
```

```python
# app/models/post.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to, validates


class Post(ApplicationModel):
    belongs_to("author")
    validates("title", presence=True)
```

Create the tables through migrations:

```sh
flask generate model Author name:string
flask generate model Post title:string author:references
flask db:prepare
```

Model/scaffold generators write migrations and behavioral model files. Successful
`db:migrate`, `db:prepare`, and `db:rollback` regenerate `db/schema.py` from the
selected database. Commit it, but **do not edit it manually**. Use
`flask db:schema:dump` to refresh it independently. See [CLI](../other/cli.md).

The snapshot lives alongside migrations in `db/`, matching Rails conventions.
For an existing app with `app/schema.py`, run `flask db:schema:dump`, remove the
old snapshot, and restart servers and workers. No database changes are needed.

The snapshot contains metadata for tables, columns, keys, constraints, indexes,
and server defaults, including tables without a behavioral model. It contains no
model behavior, validators, or relationship choices. `Post` conventionally maps
to `posts`; a model may set `__table_name__ = "legacy_posts"` for another table.

## Class-body declarations

Import declaration functions explicitly and call them inside the class body.
Aliases and module-qualified imports work normally. Repeated declarations
accumulate in source order: several `validates(...)` calls may validate the same
attribute. Association names must remain unique.

Declarations are collected, not bound immediately. Callbacks may name methods
defined later in the class, and associations need not resolve during import.
Abstract model bases, ordinary Python mixins, and `Concern` classes may contribute
declarations. Each receiving class binds its own configuration; shared ancestors
are visited once, base-first in left-to-right order, without mutating parents or
siblings. Controllers and mailers use the same declaration mechanism.

Call declarations directly in a class body. A class-body `for` loop is supported;
comprehensions, module-level calls, ordinary helper functions, and runtime methods
raise `ProgrammerError` rather than silently losing declarations. Every direct
factory call registers, even if its return value is assigned or passed elsewhere.

For a reusable declaration helper, use `@declaration`. Its factory returns a
binding callable accepting the receiving class, and may compose other declaration
factories without registering their inner calls separately:

```python
from app.models.application_model import ApplicationModel
from flaskteroids import declaration
from flaskteroids.model import validates


@declaration
def required(field):
    return validates(field, presence=True)


class Product(ApplicationModel):
    required("name")
    required("sku")
```

## Lazy mapping and normal startup

Importing a model only collects its class-body declarations. It does not require
a snapshot or connect to the database. Mapping happens when needed:
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
posts = Post.all()                      # A lazy query
posts = Post.where(title="First")       # A filtered lazy query
records = list(posts)                   # Execute and obtain a list of Post objects
posts = Post.where(Post.title.ilike("a%"))
page = posts.order(title="asc").limit(20).offset(40)
count = page.count()
first = page.first()
last = page.last()
```

Queries are lazy and **immutable**. Chain or assign the returned query; a call to
`query.where(...)` does not change the original query. `all()` always returns a
lazy query, including when called on an existing scope; it never executes SQL.
Iterating a query loads its selected records. Use `list(query)` when you need a
list. Queries are reusable; each iteration executes again rather than caching
results. Default ordering is ascending primary key; `order()` also accepts native
SQLAlchemy ordering expressions. Limits and offsets must be nonnegative or `None`.
`count()` respects the selected scope/page. `first()` returns one record or `None`;
`last()` materializes the selected scope to honor custom ordering and pagination.

Use eager loading to avoid per-row relationship queries:

```python
posts = Post.includes("author")
authors = Author.includes("posts.author")
records = list(posts)
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
or a later commit. This also applies to valid edits never explicitly
saved, and to edits made after an earlier save.

A standalone `save()` validates, flushes, and **commits before returning**.
`create()` and `update()` use that same boundary. Associated rows persisted by the
save share its transaction. Failure or a halted callback rolls back a standalone
operation; earlier successful standalone saves remain committed.

Use an explicit transaction to group operations:

```python
with Author.transaction():
    author = Author.create(name="Ada")
    post = Post.create(title="First", author=author)
    if post.errors:
        raise ValueError("Post is invalid")
# Both writes commit here; an escaping exception rolls both back.
```

Saves inside an explicit transaction join it without committing. A `False` return
does not abort that outer transaction; raise an exception when the group must
fail together. Nested `Model.transaction()` blocks also join by default. Use
`Model.transaction(requires_new=True)` for a savepoint, catching failures outside
that inner block if the outer operation should continue. After-commit callbacks
wait for the outer commit, not savepoint release. Transactions are shared across
models in the same application, not scoped to the class naming the block.

`save(validate=False)` explicitly bypasses validation. Database constraints remain
authoritative: integrity errors propagate rather than becoming validation errors.
Standalone failures clean up their transaction. If a database exception is caught
inside an explicit block, recover/roll back that transaction before further writes.
A preceding query does not turn a standalone save into an explicit transaction.

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import validates


class Product(ApplicationModel):
    validates("title", presence=True, length={"minimum": 3, "maximum": 100})
    validates("quantity", numericality={"only_integer": True})
    validates("quantity", comparison={"greater_than_or_equal_to": 0})
    validates("email", confirmation=True)
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

## Association declarations

Call association declarations directly inside the model class:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to, has_many, has_one


class Post(ApplicationModel):
    belongs_to("author", class_name="User", foreign_key="author_id")
    has_many("comments", dependent="destroy")
    has_one("preview", class_name="Preview", foreign_key="post_id")
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

Declared `has_many` associations expose a collection API backed by SQLAlchemy's
own collection storage and identity map. Assignment, append/remove, iteration,
and native eager loaders still work. Scoped queries do not load the whole
collection:

```python
post = author.posts.create(title="Next")
post = author.posts.where(title="Next").first_or_create()
author.posts.where(title="Next").count()
```

`create()` saves through the framework and returns the record, including errors
and entered values on validation failure. `first_or_create()` returns the first
matching record or creates one; keyword equality filters supply creation values.
Additional creation attributes are used only when no record matches. SQL
expressions filter queries but are not inferred as creation attributes. The
association's parent is authoritative even if attributes contain another parent
or foreign key. Creating through an association requires a saved parent;
`author.posts.new(...)` can build an unsaved graph instead. `Post.create(author=author,
...)` remains supported. Related new framework objects are validated before their
staged scalars are published by a framework save.

These find-then-create operations are not atomic uniqueness guarantees. Use a
database unique constraint where concurrent duplicate creation must be rejected.
Native `relationship()` declarations retain their native collection API.

Relationship mutations are **not scalar staging**: they have native unit-of-work
semantics. A failed scalar validation does not undo a prior collection edit. When
abandoning an invalid transient child, remove it from the collection; do not leave
an unpublished new object pending in the session. For coherent inverse updates,
assign the relationship itself; raw foreign-key edits may require reloading cached
relationships, just as with native SQLAlchemy.

### Deletion

`record.destroy()` runs framework destroy callbacks and commits a standalone
deletion before returning. Like `save()`, it joins an explicit transaction when
one is open. `dependent="destroy"` calls related records' framework `destroy()`
methods, including their callbacks and attachment cleanup, in the same boundary.
A halted standalone destruction returns `False` and rolls back earlier dependent
deletions. Inside an explicit transaction, raise on rejection when the whole group
must roll back.

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
retained. There is **no automatic request-wide transaction**. An exception or HTTP
error after a successful standalone save does not undo its commit. Context teardown
rolls back unfinished work and closes the session; it never commits native writes.

`from flaskteroids.db import transaction` exposes the same transaction context as
`Model.transaction()`. Native `with session.begin():` blocks are also respected;
use the framework context when a previous read has already implicitly opened a
SQLAlchemy transaction. Native writes require an explicit transaction or an
explicit `session.commit()`. A framework save flushes the session's published
work, including native pending changes, so use explicit boundaries when mixing
the two APIs. Caller-created sessions are caller-owned.

## Callbacks and authentication

Call `before_validation(...)`, `before_save(...)`, and other callback declarations
inside the model class.
Supported operation callbacks include before/after validation; before/around/after
save, create, update, and destroy; after initialize/find; and after commit/rollback.
Around callbacks are generators that yield once. Before callbacks returning
`False` halt their operation. Callback bodies can update staged scalar attributes.

Load callbacks run when an object is actually hydrated, not on every query that
returns an already-loaded identity. After-find runs before after-initialize on
hydration. Commit/rollback callbacks are queued by successful framework operations
and are transaction-scoped; after-commit runs only after the outer commit, not a
flush/savepoint. Commit callbacks can query associations and use the ordinary
framework persistence API in a new transaction, with the same session identity
map. Exceptions propagate, but cannot undo the transaction already committed.
Native and bulk writes do not imply these framework hooks.

### Saved changes

After a successful framework save, `record.saved_changes` maps changed scalar
attribute names to `(old_value, new_value)` tuples. Values are typed and include
database-assigned IDs/defaults. `record.saved_change_to_attribute(name)` returns
that tuple or `None`; `record.attribute_before_last_save(name)` returns the old
value, or the published value when unchanged. These APIs are available in
`after_save` and `after_commit` callbacks without inspecting SQLAlchemy history:

```python
class Product(ApplicationModel):
    after_commit("_notify_subscribers", on="update", if_="_back_in_stock")

    def _back_in_stock(self):
        change = self.saved_change_to_attribute("inventory_count")
        return change is not None and change[0] == 0 and change[1] > 0

    def _notify_subscribers(self):
        for subscriber in self.subscribers:
            ProductMailer.with_params(
                product=self, subscriber=subscriber
            ).in_stock().deliver_later()
```

Saved changes describe the latest successful save, not pending assignments or a
transaction-wide diff. Failed validations preserve that history; a successful
unchanged save replaces it. A rollback clears the rolled-back history, and
`reload()` clears it too. When a record is saved repeatedly in one transaction,
the commit callback sees its last successful save in that transaction. Rolled-back
savepoints do not replace an outer save's commit history. Native publication and
bulk writes do not produce framework saved-change history.

Use `PasswordAuthenticator` and call `has_secure_password()` inside the model
class for password behavior; a custom field name such as
`has_secure_password("passcode")` is supported.
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
