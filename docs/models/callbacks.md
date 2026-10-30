# Model callbacks

Callbacks run shared behavior at points in a record's lifecycle. For example, a
product can notify subscribers after its stock changes, regardless of which
controller saved it.

After reading this guide, you will know how to:

- Declare a callback and choose when it runs.
- Limit a callback with a condition.
- Inspect saved changes and run side effects after commit.

This guide assumes you can [create and save models](index.md). For callbacks
around HTTP requests, see [Controller callbacks](../controllers/index.md#controller-callbacks).

## Start with a save callback

Declare the callback inside the model and define its method on the same class:

```python
# app/models/author.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import before_save


class Author(ApplicationModel):
    before_save("_normalize_name")

    def _normalize_name(self):
        if self.name:
            self.name = self.name.strip()
```

Saving an author now normalizes its name before writing it. Keep callbacks for
behavior that should accompany every save; call a regular method when the
behavior belongs to just one application workflow.

## Choose a callback

Choose the lifecycle event that matches the behavior. Available events include:

- Before/after validation.
- Before/around/after save, create, update, and destroy.
- After initialize/find.
- After commit/rollback.

Before callbacks can return `False` to halt an operation. Around callbacks are
generators that yield once. A callback can assign attributes before saving.

### Conditional callbacks

Use `when` to run a callback only when a condition is true. In the `Author`
example, replace the callback declaration and add this condition method:

```python
    before_save("_normalize_name", when="_needs_normalization")

    def _needs_normalization(self):
        return self.name is not None and self.name != self.name.strip()
```

Use `unless` instead when a true condition should skip the callback. A condition
can be a method name or a callable receiving the record.

### Callback timing

After-find runs before after-initialize when a record is loaded from the database.
These load callbacks do not rerun when a query returns an already-loaded object.

After-commit callbacks wait for the outer transaction to commit. They do not
run when a nested savepoint is released. Native and bulk writes do not trigger
framework save or commit callbacks.

### Saved changes

Use `saved_change_to_attribute()` to compare the old and new values after a
successful save. It returns a pair of values, or `None` when the attribute did
not change.

For example, notify subscribers when stock goes from zero to a positive number.
This example assumes the product's inventory field, subscribers, and mailer
from the [Restock notifications tutorial](../tutorial/restock_notifications.md):

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
change in a transaction. After repeated saves in one transaction, the commit
callback sees the last successful save. Rollback and `reload()` clear saved
changes; native and bulk writes do not produce them.

## Choose the right callback for side effects

Use `after_commit` for work that leaves the database, such as enqueueing email.
At that point the worker can read the saved records. A failure in an
after-commit callback cannot undo the completed commit.

New attachment uploads are also available after commit, not in `after_save`.
See [Attachments](../other/attachments.md#when-files-become-available).

## Next steps

Follow [Restock notifications](../tutorial/restock_notifications.md) to build a
complete callback-driven email feature, or read [Background jobs](../other/jobs.md)
to move work out of a request.
