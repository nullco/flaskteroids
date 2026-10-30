# Model associations

Associations connect related models. An author has many posts; a post belongs
to an author. Declare those relationships once, then use them to find, build,
and save related records.

After reading this guide, you will know how to:

- Declare one-to-many and one-to-one relationships.
- Build and query records through an association.
- Model a many-to-many relationship with a join model.
- Save related records from a nested form.

This guide builds on [Model basics](index.md). Create the related tables through
migrations before using their associations.

## Association declarations

Declare both sides of the relationship in their model classes:

```python
# app/models/author.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_many, validates


class Author(ApplicationModel):
    has_many("posts", dependent="destroy")
    validates("name", presence=True)
```

```python
# app/models/post.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to, validates


class Post(ApplicationModel):
    belongs_to("author")
    validates("title", presence=True)
```

Generate `Post` with `author:references` to add its `author_id` foreign key.
Names and keys are inferred by convention. Use `class_name` or `foreign_key`
when the schema uses different names. Associations require single-column
primary keys.

A `belongs_to` target is required by default. Use `optional=True` when a record
can exist without it. For a single related record, use `has_one("profile")`
instead of `has_many("profiles")`, with the foreign key on the profile table.

Assign the relationship rather than just its foreign key to keep both sides
consistent:

```python
author = Author.create(name="Ada")
post = Post.new(title="First", author=author)
post.save()
```

## Work through a collection

An association keeps queries scoped to its owner:

```python
post = author.posts.create(title="Next")
posts = author.posts.where(title="Next").order(title="asc")
first_post = author.posts.first()
post_count = author.posts.count()
```

`create()` requires a saved parent and returns the child even if validation
fails. Check its errors just as you would after `Post.create()`. To build a
parent and child before saving either, use `new()`:

```python
author = Author.new(name="Grace")
author.posts.new(title="First")
author.save()
```

Saving the parent validates and saves its new children in the same transaction.
By default, it does not save edits to existing children. Use `autosave=True`
on an association when those edits should be saved with the parent.

### Query saved records or read the current collection

A collection can contain unsaved additions as well as saved records.

- `count()` counts saved rows.
- `len(author.posts)` loads the collection, including unsaved additions.
- `size()` uses loaded contents when available; otherwise it counts saved rows
  plus pending new records.
- `first()` and `last()` use loaded contents when available. An explicit query,
  such as `author.posts.order(title="asc").first()`, selects saved rows.

Filters and ordering return a new query; keep the result. They do not rearrange
an already-loaded collection.

### Refresh a collection

Use `author.posts.reload()` to replace its visible contents with fresh saved
records, without discarding the author's own pending fields or errors.
Previously held child objects keep their input and remain saveable.

Use `author.reload()` instead when you want to abandon the owner's loaded input
graph. Reloading does not save or delete records.

## Many-to-many relationships through a join model

Use a join model when the relationship has data of its own. An organization
has users through memberships, and each membership records the user's role.

Generate the models and migrate their tables:

```sh
bin/flask generate model Organization name:string
bin/flask generate model User name:string
bin/flask generate model Membership organization:references user:references role:string
bin/flask db:migrate
```

Add these declarations to the generated classes, importing `has_many`,
`belongs_to`, and `validates` from `flaskteroids.model` in the files that use
them:

```python
class Organization(ApplicationModel):
    has_many("memberships", dependent="destroy")
    has_many("users", through="memberships")


class Membership(ApplicationModel):
    belongs_to("organization")
    belongs_to("user")
    validates("role", presence=True)


class User(ApplicationModel):
    has_many("memberships", dependent="destroy")
    has_many("organizations", through="memberships")
```

Create the relationship with its role, then query the related users:

```python
organization = Organization.create(name="Example")
user = User.create(name="Ada")
organization.memberships.create(user=user, role="administrator")
members = organization.users.where(name="Ada")
```

The source association is inferred from the collection name. For a different
name, use `has_many("members", through="memberships", source="user")`.

### Build, add, and remove targets

When collection operations do not need additional membership input, you can
work directly with users:

```python
organization.users.append(existing_user)
organization.users.remove(existing_user)
```

For the membership above, first give `role` a database default in a migration;
otherwise the new membership fails its presence validation.

For a saved owner, through-collection creation, append, removal, clear, and
replacement write immediately. They commit before returning or join an explicit
transaction. Adding an existing target also saves its pending scalar edits.

A rejected append or replacement raises `RecordInvalid` from
`flaskteroids.model`. Inspect `error.record.errors` to show the failing target
or membership's errors. Let the exception escape a transaction block if the
whole group should roll back.

Removing a user deletes memberships, not the user. It does not run membership
destroy callbacks; explicitly destroy the membership when those callbacks are
needed. Add a database unique constraint on the two foreign keys if the same
membership must not appear twice.

Through collections cache their loaded targets. After changing a membership
directly, call `organization.users.reload()` to see the updated membership.
Reloading this collection leaves pending joins in `organization.memberships`;
use `organization.reload()` to abandon the whole loaded input graph.

Through associations support a direct `has_many` join and a direct
`belongs_to` source. Nested through paths and polymorphic sources are not
supported.

## Autosave and nested attributes

Nested attributes let one form edit a parent and its children. Opt in on the
parent model after declaring the association:

```python
# app/models/order.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import accepts_nested_attributes_for, has_many


class Order(ApplicationModel):
    has_many("line_items", dependent="destroy")
    accepts_nested_attributes_for(
        "line_items", allow_destroy=True, reject_if="all_blank", limit=20
    )
```

This enables autosave for the association. Assign child input, then save the
parent:

```python
order.line_items_attributes = [
    {"id": existing_item.id, "quantity": "3"},
    {"description": "New item", "quantity": "1"},
    {"id": removed_item.id, "_destroy": "1"},
]
if not order.save():
    messages = order.errors["line_items[0].quantity"]
```

An `id` updates only a child in this association; unrelated or missing IDs raise
`RecordNotFoundException`. Without an ID, input builds a new child.
`allow_destroy=True` permits deletion of an existing child on save.
`reject_if="all_blank"` ignores empty rows, and `limit=20` bounds the number
of submitted rows.

The parent and participating children validate and save together. Failed
validation retains their original input and errors for redisplay. Nested
attributes require a single primary key named `id`. For a through association,
accept nested attributes on the join model (`memberships`), not the targets
(`users`).

Continue with [Nested forms](../other/forms.md#nested-forms) to build the fields
and permit their parameters.

## Association changes and validation failures

Association edits are not staged like scalar attributes. A failed validation
does not undo an earlier append or removal. Remove an abandoned invalid new
child from the collection instead of leaving it pending.

A standalone parent save commits the related records together. Inside an
explicit transaction, a `False` result does not abort the block: raise an
exception if the group must roll back. See [Transactions](index.md#transactions).

## Load associations together

When listing posts and their authors, preload the authors to avoid a separate
query for each post:

```python
posts = Post.includes("author")
for post in posts:
    print(post.author.name)
```

Use dotted paths, such as `Author.includes("posts.author")`, for nested
associations.

## Deletion

With `dependent="destroy"`, destroying an author also destroys its posts in the
same transaction, including their framework callbacks and attachment cleanup.
A rejected standalone destruction returns `False` and rolls back the operation.

Native SQLAlchemy deletion and database cascades do not run framework child
destroy callbacks. Database `ON DELETE` behavior is configured in migrations
and is not a replacement for callback-aware destruction.

## Next steps

Use [Forms](../other/forms.md) to edit related records, or
[Model callbacks](callbacks.md) to attach behavior to their lifecycle.
