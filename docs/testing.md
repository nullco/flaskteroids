# Testing

Flaskteroids provides a Rails-style testing layer powered by pytest. Installing `flaskteroids` includes pytest, pytest-xdist for parallel testing, and Playwright for system testing; no extra or development dependencies are needed. New applications include a `test/` directory, test configuration, and a GitHub Actions workflow.

Run model, controller, job, and mailer tests with:

```sh
flask test
```

Run browser tests separately, as in Rails:

```sh
flask test:system
```

Arguments are passed to pytest:

```sh
flask test -n auto
flask test test/controllers/posts_controller_test.py
```

The command selects the `test` environment and applies pending migrations to the test database before collection. Tests that inherit from a Flaskteroids test class run in a transaction that is rolled back after every test.

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

Fixtures are loaded inside the test transaction.

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

System tests use Playwright while exposing a Rails-like browser API:

```python
class PostsTest(SystemTest):
    def test_visiting_posts(self):
        self.visit(posts_path())
        self.assert_selector("h1", text="Posts")
```

The Playwright Python package is included with Flaskteroids. Its browser binaries are installed separately; install Chromium locally before running system tests for the first time:

```sh
playwright install chromium
```
