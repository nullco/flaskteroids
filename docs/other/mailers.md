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
`Mailer`. Templates match the mailer and action names:

```html
<!-- app/views/user_mailer/welcome_email.html -->
<p>Welcome, {{ user.name }}!</p>
```

Use `app/views/user_mailer/welcome_email.txt` for the plain-text part. Text and HTML
parts can be included in the same email.

## Send a message

```python
from app.mailers.user_mailer import UserMailer

UserMailer.with_params(user=user).welcome_email().deliver_now()
UserMailer.with_params(user=user).welcome_email().deliver_later()
```

`deliver_now()` sends in the current process. `deliver_later()` enqueues work;
a [job worker](jobs.md#start-a-worker) must be running to deliver it.

## Configure delivery

Sending is disabled by default. Set delivery options in application or environment
configuration. For an SMTP server that supports STARTTLS and authentication:

```python
config.mailer.perform_deliveries = True
config.mailer.default_options = {"by": "hello@example.com"}
config.mailer.smtp_settings = {
    "host": "smtp.example.com",
    "port": 587,
    "username": "your-username",
    "password": "your-password",
}
```

These credentials are placeholders. Keep real secrets in
[encrypted credentials](../configuration.md#encrypted-credentials) or your
deployment's secret management, not source control. SMTP is the default delivery
method; `config.mailer.delivery_method` can select another adapter.

The `by` option sets the email's From header. Pass it to `mail()` to override
the configured default for an individual message:

```python
return self.mail(
    to=self.user.email,
    by="team@example.com",
    subject="Welcome to My App!",
)
```

Generated tests use an in-memory mail adapter instead of SMTP. See
[mail assertions](../testing.md#jobs-and-mail).

## Parameterized mailers

`with_params(...)` supplies values through `self.params`. It does not need an HTTP
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

## Previewing and testing mailers

Previews let you inspect an email in your browser without sending it. Automated
tests check its content and delivery behavior. Both use the same mailer and
templates as your application.

### Preview emails

The mailer generator creates
`test/mailers/previews/user_mailer_preview.py` alongside your mailer and tests.
Update that file to call the `UserMailer` from above with sample data:

```python
# test/mailers/previews/user_mailer_preview.py
from app.mailers.user_mailer import UserMailer
from app.models.user import User
from flaskteroids.mailer import MailerPreview


class UserMailerPreview(MailerPreview):
    def welcome_email(self):
        user = User(name="Jane", email="jane@example.com")
        return UserMailer.with_params(user=user).welcome_email()
```

A preview method returns the message; it does not call `deliver_now()` or
`deliver_later()`. No SMTP server, job worker, or enabled delivery is needed.

Start the development server:

```sh
bin/flask run --debug
```

Visit
<http://localhost:5000/flaskteroids/mailers/user_mailer/welcome_email>
to see the rendered message. Open
<http://localhost:5000/flaskteroids/mailers> for a list of all previews.
The browser shows the sender, recipient, and subject, and lets you switch between
HTML and plain text. API-only applications have the same preview browser.

Edit `app/views/user_mailer/welcome_email.html` and refresh to see the change.
Generated development configuration enables template reloading; Flask's
`--debug` reloader picks up changes to the mailer and preview Python files.
Without `--debug`, restart the server after changing Python code.

The example uses an unsaved record so it works without creating data. You can
also query existing development records when a scenario needs them. Previews
do not load test fixtures.

### Preview scenarios

Add another method to the same preview class to inspect a different case:

```python
def welcome_email_with_long_name(self):
    user = User(
        name="A particularly long display name",
        email="jane@example.com",
    )
    return UserMailer.with_params(user=user).welcome_email()
```

This scenario appears in the index and at
`/flaskteroids/mailers/user_mailer/welcome_email_with_long_name`.
Scenario names do not have to match mailer action names.

### Preview parameters

Query-string values are available as strings in `self.params`. For example,
replace `welcome_email` with:

```python
def welcome_email(self):
    user = User.find(self.params["user_id"])
    return UserMailer.with_params(user=user).welcome_email()
```

Visit `/flaskteroids/mailers/user_mailer/welcome_email?user_id=123`, using the ID
of an existing development user. Each request gets a fresh preview instance and
parameter dictionary. Switching formats preserves query parameters; `part=html`
and `part=plain` are reserved for the browser's format selection.

### Preview discovery

Files ending in `_preview.py` are discovered recursively under
`test/mailers/previews`. No routes or registration are needed. A file under
`previews/admin/` adds an `admin/` prefix to its preview URLs. Class names drop
the `Preview` suffix and become snake case.

Each public method defined directly on a `MailerPreview` subclass is a scenario.
Methods take no arguments beyond `self` and must return a mailer's
`MessageDelivery`. Use underscore-prefixed methods for shared helpers; inherited
methods are not listed unless overridden. Rendering uses the normal mailer
callbacks, template helpers, and captured locale.

### Preview configuration

Previews are enabled by default only in the `development` environment. To add
another preview directory, append it in your application configuration:

```python
config.mailer.preview_paths.append("lib/mailer_previews")
```

Paths are relative to the application root; absolute paths also work. Assign a
new list to `preview_paths` to replace the default directories instead.

To disable previews in an environment, set this in its `configure(config)`
function:

```python
config.mailer.show_previews = False
```

`None` selects the environment default. Set `show_previews = True` to explicitly
enable previews elsewhere, such as a test application. When disabled, preview
files are not imported and the routes are absent.

**Do not expose previews publicly or enable them in production.** Preview routes
do not run application controller authentication. Preview methods and mailer
callbacks are ordinary application code: avoid writes, delivery calls, and other
side effects. The browser does not undo those effects. Email HTML is isolated in
a sandboxed frame, but the preview is not an email-client compatibility test.

### Test mailers

Preview files are support code, not automated tests. The generator separately
creates `test/mailers/user_mailer_test.py`, inheriting from `MailerTest`. Run it
with:

```sh
bin/flask test test/mailers/user_mailer_test.py
```

Generated tests collect delivered messages in memory rather than using SMTP.
See [jobs and mail assertions](../testing.md#jobs-and-mail) for delivery counts,
queued jobs, and inspecting messages through `self.deliveries`.
