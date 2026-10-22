# Mailers

Mailers inherit from `ActionMailer`. Each action sets template variables and calls `mail` with the recipient and subject.

```python
# app/mailers/user_mailer.py
from flaskteroids.mailer import ActionMailer

class UserMailer(ActionMailer):
    def welcome_email(self, user):
        self.user = user
        return self.mail(to=user.email, subject="Welcome to My App!")
```

Call `deliver_now` to send the email immediately, or `deliver_later` to enqueue a background job:

```python
# Deliver now
UserMailer().welcome_email(user).deliver_now()

# Deliver later using a background job
UserMailer().welcome_email(user).deliver_later()
```

## Mailer helper methods

Use `helper_method` to expose a private mailer method to its templates:

```python
from flaskteroids import rules
from flaskteroids.mailer import ActionMailer, helper_method

@rules(helper_method("_greeting"))
class NoticesMailer(ActionMailer):
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

Both `deliver_now()` and `deliver_later()` use the mailer's captured assigns.
Flaskteroids restores one delivery-time mailer instance without rerunning its
constructor, action, or callbacks; text and HTML parts share that instance.
Separate deliveries have separate instances, and helper failures restore the
previous rendering scope. Queued state must be serializable by the selected
queue adapter. This follows Flaskteroids' existing captured-state mail pipeline,
rather than Rails' action-reexecution model for queued mail.
