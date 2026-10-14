# Testing

Tests use pytest, pytest-xdist, and Playwright. Generated applications include a
health-endpoint integration test, test configuration, and a green pristine-app
GitHub Actions workflow. CI installs with `uv sync --locked`, runs `bin/flask test`,
provisions Chromium explicitly, and runs `bin/flask test:system`.

Both framework commands treat pytest no-tests-collected as success with an explicit
message, including filters selecting nothing. All other pytest statuses and arguments
are preserved. Invoke pytest directly for strict empty-selection status. An empty
system suite does not launch a browser.

Run model, controller, job, and mailer tests with:

```sh
bin/flask test
```

Run browser tests separately:

```sh
bin/flask test:system
```

Both commands pass arguments to pytest:

```sh
bin/flask test -n auto
bin/flask test test/controllers/posts_controller_test.py
```

The commands use the `test` environment and apply pending migrations. Tests that inherit from Flaskteroids test classes roll back database changes after each test.

File uploads use `fixture_file_upload('avatar.png')` with files in
`test/fixtures/files`. The pytest plugin uses temporary disk storage for each
test, including applications configured to use S3. Browser tests can use
`self.attach_file('Avatar', 'test/fixtures/files/avatar.png')`. See
[Attachments](other/attachments.md#tests).

## Test types

```python
from test.test_helper import (
    IntegrationTest,
    JobTest,
    MailerTest,
    ModelTest,
    SystemTest,
)
```

Generated tests use files ending in `_test.py` and classes ending in `Test`.

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
class PostTest(ModelTest):
    fixtures = ["posts"]

    def setup(self):
        self.post = self.posts("one")
```

Flaskteroids loads fixtures inside the test transaction.

## Integration tests

```python
from test.test_helper import IntegrationTest, get, post
from app.models.post import Post
from flaskteroids.routes import post_url, posts_url


class PostsControllerTest(IntegrationTest):
    fixtures = ["posts"]

    def test_should_get_index(self):
        get(posts_url())
        self.assert_response("success")

    def test_should_create_post(self):
        with self.assert_difference(Post.count):
            post(
                posts_url(),
                params={"post": {"title": "New post", "content": "Content"}},
            )

        self.assert_redirected_to(post_url(Post.last()))
```

Available request functions are `get`, `post`, `patch`, `put`, and `delete`.

## Jobs and mail

The test environment uses in-memory job and mail adapters:

```python
with self.assert_enqueued_with(job=PublishPostJob, args=[post]):
    PublishPostJob.perform_later(post)

with self.perform_enqueued_jobs():
    PublishPostJob.perform_later(post)

with self.assert_emails(1):
    PostsMailer.published(post).deliver_now()
```

No broker or SMTP server is required.

## System tests

System tests use Playwright through helpers such as `visit` and `assert_selector`:

```python
class PostsTest(SystemTest):
    def test_visiting_posts(self):
        self.visit(posts_path())
        self.assert_selector("h1", text="Posts")
```

Flaskteroids includes the Playwright Python package, but not its browser binaries. Install Chromium before your first system test run:

```sh
.venv/bin/playwright install chromium
```
