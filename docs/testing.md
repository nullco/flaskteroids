# Testing

Tests grow alongside your application. Generators give you starting tests for
new features, and your new app includes a health check to get you going.

Run model, controller, job, and mailer tests as you work:

```sh
bin/flask test
```

Use browser tests to check the journey a person takes through your app:

```sh
bin/flask test:system
```

After reading this guide, you will know how to:

- Choose the right kind of test for a behavior.
- Create fixture data and make requests in tests.
- Check background work, email, and browser journeys.

## Run a focused test

Both commands use pytest, so you can select a file or run tests in parallel:

```sh
bin/flask test -n auto
bin/flask test test/controllers/posts_controller_test.py
```

The commands select the `test` environment and apply pending migrations. Tests
that inherit from the framework's test classes roll back database changes after
each test, so records from one test do not affect the next.

For upload tests, put example files in `test/fixtures/files` and use
`fixture_file_upload('avatar.png')`. Uploads use temporary storage, leaving your
real files untouched. See [Attachments](other/attachments.md#tests) for examples.

## Test types

Import the base class you need from `test.test_helper`:

| Base class | What to test |
| --- | --- |
| `ModelTest` | Validations, queries, and model behavior |
| `IntegrationTest` | HTTP requests and responses |
| `JobTest` | Background work and enqueueing |
| `MailerTest` | Email content and delivery |
| `SystemTest` | User journeys in a real browser |

Generated files end in `_test.py`, and test classes end in `Test`. Each base class
provides an application context, fixture access, and the framework's assertions.
Use ordinary pytest assertions alongside them.

## Fixtures

Fixtures live under `test/fixtures`:

```yaml
# test/fixtures/posts.yml
one:
  title: First post
  content: First post content

two:
  title: Second post
  content: Second post content
```

Declare and access them from a test:

```python
from test.test_helper import ModelTest


class PostTest(ModelTest):
    fixtures = ["posts"]

    def setup(self):
        self.post = self.posts("one")

    def test_fixture_has_a_title(self):
        assert self.post.title == "First post"
```

Each test gets its declared fixtures, and its changes are rolled back afterward.
Use fixture labels rather than hard-coded IDs; generated IDs may have gaps.

## Integration tests

Make requests without starting a web server, then check the response or the
resulting database change:

```python
from test.test_helper import IntegrationTest, get, post
from app.models.post import Post
from flaskteroids.routes import post_url, posts_url


class PostsControllerTest(IntegrationTest):
    fixtures = ["posts"]

    def test_index_returns_success(self):
        get(posts_url())
        self.assert_response("success")

    def test_create_saves_post(self):
        with self.assert_difference(Post.count):
            post(
                posts_url(),
                params={"post": {"title": "New post", "content": "Content"}},
            )

        self.assert_redirected_to(post_url(Post.last()))
```

Available request functions are `get`, `post`, `patch`, `put`, and `delete`.

## State changes

Use `assert_changes` around an operation to check that an expression changes:

```python
with self.assert_changes(lambda: post.title, was="Draft", to="Published"):
    post.update(title="Published")
```

`was` checks the value before the block, and `to` checks the value afterward.
Both are optional; the expression must change even when neither is supplied.

## Jobs and mail

The test environment keeps queued jobs and delivered email in memory. Inside a
test method, use these helpers with your job and mailer classes:

```python
with self.assert_enqueued_with(job=PublishPostJob, kwargs={"post_id": post.id}):
    PublishPostJob().perform_later(post_id=post.id)

with self.perform_enqueued_jobs():
    PublishPostJob().perform_later(post_id=post.id)

with self.assert_emails(1):
    PostsMailer.published(post).deliver_now()
```

`assert_enqueued_with` checks that a job was scheduled. `perform_enqueued_jobs`
runs jobs enqueued inside its block. `assert_emails` checks how many messages were
delivered. Built messages are available through `self.deliveries` as
`EmailMessage` objects, so tests can inspect headers and HTML/plain-text parts.
No broker or SMTP server is required.

To inspect email appearance interactively, use
[mailer previews](other/mailers.md#preview-emails). Previews render example emails
in the development browser without delivery; they complement automated tests
rather than replacing them.

## System tests

System tests use Playwright through helpers such as `visit` and `assert_selector`.
Chromium is started lazily and reused within each system-test class. Every test
gets a fresh browser context and page, so cookies, local storage, and browser
handlers do not carry over between tests. Playwright stops after the class so
unrelated tests can use their own asyncio event loops. Database changes and
uploaded files remain isolated by the normal test lifecycle.

For example:

```python
from test.test_helper import SystemTest
from flaskteroids.routes import posts_path


class PostsTest(SystemTest):
    def test_index_shows_posts_heading(self):
        self.visit(posts_path())
        self.assert_selector("h1", text="Posts")
```

Fill fields by their labels, supplying the contents through `value`:

```python
self.fill_in("Title", value="First post")
self.fill_in_rich_text_area("Content", value="<div>Hello</div>")
```

Rich-text values are HTML, loaded through Lexxy's public value property. See
[Rich text](other/rich_text.md) for setup and model fixtures.

### Install the browser

Flaskteroids includes the Playwright Python package, but not the browser itself.
Install Chromium before running your first system test:

```sh
.venv/bin/playwright install chromium
```
