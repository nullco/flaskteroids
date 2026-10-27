# Mailers

Mail captures the locale when `mail()` is called and uses it for immediate or
queued template rendering. See [Internationalization](internationalization.md#mail-and-jobs)
for locale selection and translated subjects.

Mailers build and send email. Each action chooses a recipient and subject, and
sets the values its templates need. You can deliver the message immediately or
send it through a background job.

## Create a mailer

Generate the mailer and its templates:

```sh
bin/flask generate mailer User welcome_email
```

Add the recipient and template values to the generated class:

```python
# app/mailers/user_mailer.py
from app.mailers.application_mailer import ApplicationMailer


class UserMailer(ApplicationMailer):
    def welcome_email(self):
        self.user = self.params["user"]
        return self.mail(to=self.user.email, subject="Welcome to My App!")
```

Application mailers inherit from `ApplicationMailer`, whose base is the framework's
`ActionMailer`. Templates match the mailer and action names:

```html
<!-- app/views/user_mailer/welcome_email.html -->
<p>Welcome, {{ user.name }}!</p>
```

Use `app/views/user_mailer/welcome_email.txt` for the plain-text part. Text and HTML
parts can be included in the same email.

## Preview emails

The mailer generator also creates
`test/mailers/previews/user_mailer_preview.py`. Preview methods return example
messages without delivering them:

```python
from app.mailers.user_mailer import UserMailer
from app.models.user import User
from flaskteroids.mailer import MailerPreview


class UserMailerPreview(MailerPreview):
    def welcome_email(self):
        user = User(name="Jane", email="jane@example.com")
        return UserMailer.with_(user=user).welcome_email()

    def welcome_email_with_long_name(self):
        user = User(
            name="A particularly long display name",
            email="jane@example.com",
        )
        return UserMailer.with_(user=user).welcome_email()
```

Start the development server:

```sh
bin/flask run --debug
```

Open <http://localhost:5000/flaskteroids/mailers> to browse previews, or visit
`/flaskteroids/mailers/user_mailer/welcome_email` directly. The browser shows
message headers and HTML/plain-text alternatives. HTML is displayed in a
sandboxed frame, independently of application layouts. API-only applications
have the same preview browser.

Preview files are discovered recursively, without route declarations or manual
registration. A file under `previews/admin/` adds an `admin/` prefix to its preview
URLs. Class names drop the `Preview` suffix and become snake case. Each public
method defined directly on a preview class is a scenario; use underscore-prefixed
methods for shared helpers. Inherited methods are not listed unless overridden.
Methods take no arguments beyond `self` and must return a mailer's
`MessageDelivery`, not call `deliver_now()` or `deliver_later()`.

Query-string values are available as strings in `self.params`:

```python
def welcome_email(self):
    user = User.find(self.params["user_id"])
    return UserMailer.with_(user=user).welcome_email()
```

Visit `/flaskteroids/mailers/user_mailer/welcome_email?user_id=123`.
The browser reserves `part=html` and `part=plain` for format selection and
preserves the other query parameters when switching formats. Each request gets
a fresh preview instance and parameter dictionary.

Templates refresh when `config.enable_reloading` is enabled, as it is in generated
development configuration. Flask's `--debug` reloader picks up Python changes,
including preview source files; without it, restart after changing Python code.

Previews use the normal mailer rendering pipeline, including callbacks, helpers,
and the captured locale. They do not use SMTP, enqueue jobs, load test fixtures,
or require delivery to be enabled. Use unsaved sample records when possible, or
query existing development records when a scenario needs them. Preview files are
support code, not automated tests.

### Preview configuration

Previews are enabled by default only in the `development` environment. Disable
them explicitly, or configure additional directories relative to the application
root (absolute paths also work):

```python
config.action_mailer.show_previews = False
config.action_mailer.preview_paths = [
    "test/mailers/previews",
    "lib/mailer_previews",
]
```

`show_previews = None` selects the environment default. Set it to `True` to
explicitly enable previews in another environment, such as a test application.
When disabled, preview files are not imported and the routes are absent.

**Do not expose previews publicly or enable them in production.** Preview routes
do not run application controller authentication. Preview methods and mailer
callbacks are ordinary application code: avoid writes, delivery calls, and other
side effects. The preview browser does not undo application-side effects or
simulate how an email client will render your HTML.

## Send a message

```python
from app.mailers.user_mailer import UserMailer

UserMailer.with_(user=user).welcome_email().deliver_now()
UserMailer.with_(user=user).welcome_email().deliver_later()
```

`deliver_now()` sends in the current process. `deliver_later()` enqueues work;
a [job worker](jobs.md#start-a-worker) must be running to deliver it.

## Configure delivery

Sending is disabled by default. Set delivery options in application or environment
configuration. For an SMTP server that supports STARTTLS and authentication:

```python
config.action_mailer.perform_deliveries = True
config.action_mailer.default_options = {"from_": "hello@example.com"}
config.action_mailer.smtp_settings = {
    "host": "smtp.example.com",
    "port": 587,
    "username": "your-username",
    "password": "your-password",
}
```

These credentials are placeholders. Keep real secrets in
[encrypted credentials](../configuration.md#encrypted-credentials) or your
deployment's secret management, not source control. SMTP is the default delivery
method; `config.action_mailer.delivery_method` can select another adapter.

Generated tests use an in-memory mail adapter instead of SMTP. See
[mail assertions](../testing.md#jobs-and-mail).

## Parameterized mailers

`with_(...)` supplies values through `self.params`. It does not need an HTTP
request. Each action gets a fresh mailer instance and a shallow copy of the
parameters. Actions can also accept ordinary arguments.

Parameters do not automatically become template variables. Assign them explicitly
as instance variables, such as `self.user` in the example above.

## Delivery

For queued messages, understand what is captured now and what is loaded later:

| When | What happens |
| --- | --- |
| The action is called | Actions and callbacks run; the recipient, subject, and template values are captured |
| `deliver_now()` | Templates render using the supplied objects |
| `deliver_later()` | Saved model values are serialized as record references |
| The worker delivers | Model references are reloaded and templates render; the action does not run again |

Model references also work inside lists, tuples, and dictionaries. Other queued
values must be serializable by the queue adapter.

**Enqueue after commit** so the worker can see the records. Unsaved models raise
`SerializationError` on enqueue. A referenced record missing at delivery raises
`DeserializationError`. Both exceptions are in `flaskteroids.exceptions`.

Queued rendering ignores unsaved edits without changing the caller's objects.
Model-backed template content can therefore change before delivery, while the
captured recipient and subject stay fixed. Text and HTML parts share one
restored delivery-time mailer instance.

## Mailer helper methods

Use `helper_method` to expose a private method to mailer templates:

```python
from app.mailers.application_mailer import ApplicationMailer
from flaskteroids.mailer import helper_method


class NoticesMailer(ApplicationMailer):
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

The declaration is inherited, honors child overrides, and forwards positional and
keyword arguments. Private methods are not actions or template helpers unless
explicitly exposed. Ordinary returned text is HTML-escaped.

Use `helper(...)` for a different task: including presentation helper classes in
the view context. Those helpers can call exposed methods such as
`self.greeting()`. Mailers select helper classes explicitly; they do not inherit
request-controller helpers. See
[mailer view helpers](../views/index.md#mailers-and-rendering-outside-requests).
