# Mailers

Mailers inherit from `ActionMailer`. Each action sets template variables and calls `mail` with the recipient and subject.

```python
# app/mailers/user_mailer.py
from flaskteroids import params
from flaskteroids.mailer import ActionMailer

class UserMailer(ActionMailer):
    def welcome_email(self):
        user = params["user"]
        self.name = user.name
        return self.mail(to=user.email, subject="Welcome to My App!")
```

Call `deliver_now` to send the email immediately, or `deliver_later` to enqueue a background job:

```python
# Deliver now
UserMailer.with_params(user=user).welcome_email().deliver_now()

# Deliver later using a background job
UserMailer.with_params(user=user).welcome_email().deliver_later()
```

## Parameterized mailers

`with_params(...)` supplies action and callback inputs through the same `params`
proxy used by controllers, without requiring an HTTP request. Each action call
gets a fresh mailer and a shallow parameter copy. Action arguments remain supported.

Input params are not template assigns or queued state. Assign values needed by
templates and delivery-time helpers explicitly, as with `self.name` above, and
keep queued assigns serializable; model identities are not serialized automatically.

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

Actions and callbacks run immediately. Both delivery methods render their captured
assigns, restoring one mailer instance shared by the text and HTML parts. Unlike
Rails, queued delivery does not rerun the action.
