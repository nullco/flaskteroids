# Mailers

Mailers inherit from `ActionMailer`. Each action sets template variables and calls `mail` with the recipient and subject.

```python
# app/mailers/user_mailer.py
from flaskteroids.mailer import ActionMailer

class UserMailer(ActionMailer):
    def welcome_email(self):
        self.user = self.params["user"]
        return self.mail(to=self.user.email, subject="Welcome to My App!")
```

Call `deliver_now` to send the email immediately, or `deliver_later` to enqueue a background job:

```python
# Deliver now
UserMailer.with_(user=user).welcome_email().deliver_now()

# Deliver later using a background job
UserMailer.with_(user=user).welcome_email().deliver_later()
```

## Parameterized mailers

`with_(...)` supplies action and callback inputs through `self.params`,
an instance-owned dictionary that needs no HTTP request. Each action call gets a
fresh mailer and a shallow parameter copy. Action arguments remain supported.

Input params are not automatically template assigns. Expose values needed by
templates and delivery-time helpers explicitly, as with `self.user` above.

## Mailer helper methods

Use `helper_method` to expose a private mailer method to its templates:

```python
from flaskteroids.mailer import ActionMailer, helper_method


class NoticesMailer(ActionMailer):
    helper_method("_greeting")

    def welcome(self, name, email):
        self.name = name
        return self.mail(to=email, subject="Welcome")

    def _greeting(self, punctuation="!"):
        return f"Hello, {self.name}{punctuation}"
```

```html
<!-- app/views/notices_mailer/welcome.html -->
<p>{{ greeting() }}</p>
```

The declaration is inherited and uses child overrides. Positional and keyword
arguments are forwarded to the mailer method. Private methods are not mailer
actions or template helpers unless explicitly exposed. Returned text is escaped
normally in HTML templates.

`helper(...)` has a different purpose: it includes presentation helper classes
in the view context, whose methods can call `self.greeting()`. Mailers select
those classes explicitly rather than inheriting request-controller helpers.
See [application helpers](../views/index.md#mailers-and-rendering-outside-requests).

## Delivery

Actions and callbacks run immediately, capturing the recipient and subject.
`deliver_now()` renders the supplied objects. `deliver_later()` stores saved model
assigns as references and reloads them at delivery, including models nested in
lists, tuples, and dictionaries. Other queued assigns must be serializable by the
queue adapter.

Unsaved model assigns raise `SerializationError` on enqueue; records missing at
delivery raise `DeserializationError` (both in `flaskteroids.exceptions`). Queued
rendering ignores unsaved edits without altering the caller's objects. Enqueue
after commit so records are visible to the worker.

Text and HTML parts share one delivery-time mailer. Unlike Rails, queued delivery
does not rerun the action, so model-backed template values can change while the
captured headers remain fixed.
