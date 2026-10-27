# Models

Models represent your application's data and the rules for working with it.
Use them to query records, validate input, manage associations, and save changes.

Define columns in database migrations and behavior in model classes. Flaskteroids
reads column definitions from the generated `db/schema.py`; you do not repeat
them in your models. SQLAlchemy is available for advanced queries and integration,
but ordinary model work does not require managing a session.

## Define models and migrate

Application models inherit from the generated abstract base:

```python
# app/models/application_model.py
from flaskteroids.model import Model


class ApplicationModel(Model):
    __abstract__ = True
```

Generate models and their migrations from your application directory:

```sh
bin/flask generate model Author name:string
bin/flask generate model Post title:string author:references
bin/flask db:prepare
```

Add behavior to the generated classes:

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

`Post` uses the `posts` table by convention. Set
`__table_name__ = "legacy_posts"` to use a different table.

### The schema snapshot

Successful `db:migrate`, `db:prepare`, and `db:rollback` commands regenerate
`db/schema.py` from the selected database. **Commit the snapshot, but do not edit
it by hand.** To refresh it without migrating, run `bin/flask db:schema:dump`.
Restart servers and workers after migrations so they load the new definitions.
See [database commands](../other/cli.md#database-preparation).

The snapshot describes tables, columns, keys, constraints, indexes, and server
defaults, including tables with no model class. It does not contain validations,
associations, or other model behavior.

If an older application has `app/schema.py`, dump the snapshot to `db/schema.py`,
remove the old file, and restart. This move does not require database changes.

## Queries

```python
post = Post.find(1)                     # Raises RecordNotFoundException if absent
post = Post.find_by(title="First")      # Returns None if absent
posts = Post.all()                      # A query, not a list
posts = Post.where(title="First")
records = list(posts)                   # Load the selected records
posts = Post.where(Post.title.ilike("a%"))
page = posts.order(title="asc").limit(20).offset(40)
count = page.count()
first = page.first()
last = page.last()
```

Queries are **lazy**: building a query does not load records. Iteration and methods
such as `first()` or `count()` execute it. `all()` also returns a lazy query, even
when called on an existing query.

Queries are **immutable**: keep the returned query when adding filters or ordering.
Calling `posts.where(...)` alone does not change `posts`.

Other query behavior to keep in mind:

- Each iteration executes the query again; results are not cached.
- Default ordering is ascending primary key. `order()` also accepts SQLAlchemy
  ordering expressions.
- Limits and offsets must be nonnegative or `None`.
- `count()` counts the selected scope, including its limit and offset.
- `first()` returns a record or `None`. `last()` loads the selected scope to
  respect custom ordering and pagination.

### Load associations together

Use `includes()` to avoid a separate association query for each record:

```python
posts = Post.includes("author")
authors = Author.includes("posts.author")
records = list(posts)
```

Dotted paths load nested associations using SQLAlchemy select-in loaders.
Unknown relationships raise `AttributeError`; malformed paths raise `ValueError`.
For more complex queries, use `query.statement`, `query.options(...)`, or native
SQLAlchemy.

## Assignment, validation, and persistence

Build a record, then check the result of saving it:

```python
post = Post.new(title="First", author=author)
if post.save():
    identifier = post.id
else:
    messages = post.errors.full_messages()
```

`create()` builds and saves in one call. It returns the record even if validation
fails. `update()` assigns attributes and returns whether saving succeeded:

```python
post = Post.create(title="", author=author)
assert post.errors
assert post.update(title="Fixed")
```

### Unsaved changes

Assigning a scalar attribute changes what you read on that object, but does not
publish it for database writes until a successful save. This is called **staging**.
Invalid input and its errors remain available for correction and form redisplay.
Another object's save or a later commit does not accidentally save these edits.
This also applies to valid edits you have not explicitly saved.

- `reload()` loads saved state and discards pending scalar input and errors.
- `discard_changes()` discards pending scalar input without refreshing saved state.
- Native SQLAlchemy refresh/expiration does not clear staged input by itself.

### Transactions

A standalone `save()`, `create()`, or `update()` **commits before returning**.
Associated rows saved by the operation share its transaction. A failure or halted
callback rolls back that operation, not earlier successful standalone saves.

Use an explicit transaction when several operations must succeed together:

```python
with Author.transaction():
    author = Author.create(name="Ada")
    post = Post.create(title="First", author=author)
    if post.errors:
        raise ValueError("Post is invalid")
# Both writes commit here; an exception escaping the block rolls both back.
```

Saves inside the block join its transaction without committing individually.
**A `False` save result does not abort the block**; raise an exception when the
whole group should roll back. Transactions cover all models in the application,
not just the class used to open the block.

Nested `Model.transaction()` blocks join the outer transaction by default. Use
`requires_new=True` for a savepoint. Catch a failure outside the inner block if
the outer operation should continue. After-commit callbacks wait for the outer
commit, not savepoint release.

`save(validate=False)` skips validation, not database constraints. Integrity
errors propagate as exceptions rather than model errors. Standalone failures
clean up their transaction. After a database error inside an explicit transaction,
roll back/recover that transaction before further writes. An earlier query does
not turn a later standalone save into an explicit transaction.

### Validations

Declare user-facing rules in the model class:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import validates


class Product(ApplicationModel):
    validates("title", presence=True, length={"minimum": 3, "maximum": 100})
    validates("quantity", numericality={"only_integer": True})
    validates("quantity", comparison={"greater_than_or_equal_to": 0})
    validates("email", confirmation=True)
```

Validators run in declaration order. `confirmation=True` adds a writable
confirmation field. `is_valid()` checks the rules without publishing input.
`errors` is truthy when populated; use `errors.count` and
`errors.full_messages()` to inspect it. Its JSON representation is a list of
full messages.

Assignment converts supported scalar types, but casting is not validation.
Numericality checks the original input, so a permissive numeric conversion does
not make malformed input valid. `numericality={"allow_none": True}` permits
`None`, not blank strings.

Use `read_attribute_before_type_cast(name)` or `attributes_before_type_cast` to
inspect original input. Model-backed forms use it when redisplaying failed
submissions. See [Fields](../other/fields.md) and [Forms](../other/forms.md).

### Defaults

Put persistent defaults in migrations. Simple literal database defaults are
available on new objects without a query. Database functions, computed columns,
and generated IDs populate on flush. Explicit `None` does not request a default;
JSON retains its native JSON-null behavior.

`save()` maintains declared `created_at` and `updated_at` attributes. Native
writes do not run this timestamp behavior automatically.

Python default functions cannot be recovered from the database snapshot. Use
assignment or initialization callbacks for application-side defaults, rather
than `Column.default` definitions or edits to `db/schema.py`.

## Association declarations

Declare relationships inside the model class:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to, has_many, has_one


class Post(ApplicationModel):
    belongs_to("author", class_name="User", foreign_key="author_id")
    has_many("comments", dependent="destroy")
    has_one("preview", class_name="Preview", foreign_key="post_id")
```

Names and foreign keys are inferred by convention. Supply `class_name` or
`foreign_key` when your schema differs. `belongs_to()` requires a target by
default; use `optional=True` to allow its absence. Use `inverse_of="posts"` when
Flaskteroids cannot infer the inverse association unambiguously.

These declarations require single-column primary keys. Use native SQLAlchemy
relationships for more complex joins.

```python
post.author = author
assert post in author.posts
post.save()

post = Post.create(title="Next", author=author)
```

### Work through a collection

A `has_many` collection supports assignment, append/remove, iteration, and native
eager loading. You can query it without loading the entire collection:

```python
post = author.posts.create(title="Next")
post = author.posts.where(title="Next").first_or_create()
author.posts.where(title="Next").count()
```

- `create()` saves the record and returns it, including input and errors if invalid.
- `first_or_create()` finds the first match or creates a record. Keyword equality
  filters supply creation values; SQL expressions do not. Additional creation
  attributes are used only when no match exists.
- The collection's parent wins over a conflicting parent or foreign key in input.
- Creating through a collection requires a saved parent. Use
  `author.posts.new(...)` to build an unsaved graph. `Post.create(author=author,
  ...)` is also supported. Framework saves validate related new objects before
  publishing their staged scalar values.

Find-then-create is not an atomic uniqueness guarantee. Add a database unique
constraint when concurrent duplicates must be rejected.

### Association changes and validation failures

Association edits are **not staged like scalar attributes**. A failed validation
does not undo an earlier append or removal. If you abandon an invalid new child,
remove it from the collection rather than leaving it pending in the session.

Assign relationships (`post.author = author`) to keep both sides consistent.
Editing a raw foreign key may require reloading cached relationships. Collections
use SQLAlchemy's own storage and identity map; native `relationship()`
declarations keep their native collection API.

### Deletion

`record.destroy()` runs destroy callbacks and commits before returning, unless
it is inside an explicit transaction. `dependent="destroy"` calls related
records' framework `destroy()` methods in the same transaction, including their
callbacks and attachment cleanup.

A halted standalone destruction returns `False` and rolls back earlier dependent
deletions. Inside an explicit transaction, raise an exception if rejection should
roll back the whole group.

Native `session.delete()` and ORM/database cascades do not automatically run
framework child destroy callbacks. Configure database `ON DELETE` behavior in
migrations; it is not a replacement for callback-aware destruction.

## Callbacks and authentication

Callbacks run at points in a record's lifecycle. Import declarations explicitly
and call them inside the model class, such as `before_save("_normalize_name")`.

Supported callbacks include:

- Before/after validation.
- Before/around/after save, create, update, and destroy.
- After initialize/find.
- After commit/rollback.

Before callbacks can return `False` to halt an operation. Around callbacks are
generators that yield once. Callback methods can change staged scalar attributes.

### Conditional callbacks

Use `when` to run a callback only when a condition is true, or `unless` to skip
it when a condition is true:

```python
before_save("_normalize", when="_needs_normalization", unless="_importing")
```

A condition can be a method name or a callable receiving the record. Lists are
also supported: every `when` condition must pass, and no `unless` condition may
pass.

### Callback timing

After-find runs before after-initialize when a record is loaded from the database.
These load callbacks do not rerun when a query returns an already-loaded object.

Successful framework operations queue commit/rollback callbacks for their
transaction. After-commit runs only after the outer commit, not a flush or
savepoint. It can query associations and save records in a new transaction using
the same session identity map. An exception there propagates, but cannot undo
the completed commit. Native and bulk writes do not trigger these framework hooks.

### Saved changes

After a successful save, inspect changes without using SQLAlchemy attribute history:

| API | Result |
| --- | --- |
| `record.saved_changes` | Changed scalar names mapped to `(old_value, new_value)` tuples |
| `record.saved_change_to_attribute(name)` | That attribute's tuple, or `None` |
| `record.attribute_before_last_save(name)` | Its old value, or its published value if unchanged |

Values are typed and include database-assigned IDs and defaults. These APIs are
available in `after_save` and `after_commit`:

```python
from app.mailers.product_mailer import ProductMailer
from app.models.application_model import ApplicationModel
from flaskteroids.model import after_commit


class Product(ApplicationModel):
    after_commit("_notify_subscribers", on="update", when="_back_in_stock")

    def _back_in_stock(self):
        change = self.saved_change_to_attribute("inventory_count")
        return change is not None and change[0] == 0 and change[1] > 0

    def _notify_subscribers(self):
        for subscriber in self.subscribers:
            ProductMailer.with_params(
                product=self, subscriber=subscriber
            ).in_stock().deliver_later()
```

Saved changes describe the latest successful save, not pending input or every
change in a transaction. Failed validation preserves the history; a successful
unchanged save replaces it. Rollback and `reload()` clear it. After repeated saves
in one transaction, the commit callback sees the last successful save. A rolled-back
savepoint does not replace an outer save's commit history. Native publication and
bulk writes do not produce this history.

### Passwords

Use `PasswordAuthenticator` with `has_secure_password()` for password behavior.
A custom field such as `has_secure_password("passcode")` is supported. For the
complete login workflow, use the
[authentication generator](../other/cli.md#authentication).

Authentication and reset-token checks use saved digests, so an invalid password
edit does not invalidate existing credentials. Passwords, digests, confirmations,
and reset tokens are excluded from default JSON and forms. Raw-input APIs remain
sensitive: do not log them.

Attachment uploads happen after commit; see [Attachments](../other/attachments.md)
for upload and rollback behavior.

## Encrypted attributes

Use `encrypts("notes")` for randomized string/text encryption. Use
`encrypts("email", deterministic=True, downcase=True)` when equality lookups are
needed. Assignment, validations, and forms still work with plaintext; database
storage uses ciphertext.

Rich-text encryption uses the same service and dedicated keys. See
[Attribute encryption](encryption.md) for setup, queries, key rotation, and limits.

## Temporary attributes and serialization

For a value that should not be saved, declare a class default, a property with a
setter, or a private cache name. Initialize mutable caches per instance. Unknown
public assignments raise `AttributeError`, and framework methods/metadata cannot
be replaced through assignment.

Temporary values are not automatically saved or serialized. Repeated lookups in
one session return the same object, including its temporary state.

Default JSON includes mapped scalar attributes and staged values, but excludes
authentication secrets and virtual fields. Override `__json__()` for a custom
response, or add names to the `_serialization_exclude` set. Form values are
independent of JSON serialization. Ordinary editors/type checkers generally
cannot infer dynamically mapped fields.

## Class-body declarations

This section explains advanced declaration reuse; ordinary models can use the
examples above.

Import declaration functions and call them directly in a class body. Aliases and
module-qualified imports work. Repeated declarations accumulate in source order;
several `validates(...)` calls may apply to one attribute. Association names must
be unique.

Declarations are collected before they are bound, so callbacks can name methods
defined later and associations need not resolve during import. Abstract bases,
ordinary mixins, and `Concern` classes can contribute declarations. Each receiving
class gets its own configuration without changing parents or siblings. Shared
ancestors are visited once, base-first and left-to-right. Controllers and mailers
use the same mechanism.

Class-body `for` loops work. Calls from comprehensions, module scope, ordinary
helper functions, or runtime methods raise `ProgrammerError`. Every direct factory
call registers, even if you assign or pass along its return value.

For a reusable declaration helper, use `@declaration`. Its factory returns a
callable that accepts the receiving class. It may compose other factories without
registering the inner calls separately:

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

Importing a model collects declarations without connecting to a database or
requiring a schema snapshot. Mapping happens when you construct a record, query
it, or access an expression such as `Post.title`.

This lets startup and migration commands import new models before their tables
exist in the snapshot. Initializers still run normally; an initializer that uses
an unavailable model fails with migration guidance.

Mapping reads the snapshot, not the live database. Restart servers and workers
after migrations; do not reload schema files or change active mappings in place.
Abstract bases need no table. Concrete model inheritance, duplicate model names
in one application model set, and columns that shadow model APIs are rejected.
Model sets have isolated registries; matching schemas can use the same mapped
classes with separate engines and sessions.

## Native SQLAlchemy and transactions

Use native SQLAlchemy when you need more control. Framework and native queries
return the same mapped objects within a session:

```python
from sqlalchemy import inspect, select
from sqlalchemy.orm import selectinload
from flaskteroids.db import session

Author.prepare()  # Map without database access before using bare native APIs.
mapper = inspect(Author)
author = session.get(Author, 1)
authors = session.scalars(select(Author).options(selectinload(Author.posts))).all()
assert Author.find(author.id) is author
```

Mapped columns and relationships are real SQLAlchemy attributes. The important
boundary is staged scalar input: SQL predicates and SQLAlchemy history describe
**published state**, not pending `record.changes`. Use
`read_published_attribute(name)` to read that state directly.

To publish input without validation or framework callbacks:

```python
post = Post(title="Native", author=author).apply_changes()
session.add(post)
session.flush()
```

Adding a new record with unpublished staged input is rejected at flush instead
of silently inserting null/default values. Native/bulk operations bypass
framework validations and operation callbacks. In-place mutable edits use native
SQLAlchemy tracking; reassign a scalar when you want staged edits.

### Session ownership

- Sessions belong to application contexts. Autoflush is disabled and committed
  attributes are retained.
- There is **no automatic request-wide transaction**. An HTTP error after a
  successful standalone save does not undo its commit.
- Context exit rolls back unfinished work and closes the session. It never commits
  native writes.
- Native writes need an explicit transaction or `session.commit()`.

`flaskteroids.db.transaction` is the same context manager as
`Model.transaction()`. Native `with session.begin():` blocks are respected too;
prefer the framework context if an earlier read already opened an implicit
SQLAlchemy transaction.

A framework save flushes published session work, including native pending changes.
Use explicit boundaries when mixing the two APIs. Caller-created sessions remain
the caller's responsibility.
