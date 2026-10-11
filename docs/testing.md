# Testing

Flaskteroids uses pytest with Rails-style test classes and assertions. The package includes pytest, pytest-xdist for parallel runs, and Playwright for browser tests. Generated applications include a `test/` directory, test configuration, and a GitHub Actions workflow.

Run model, controller, job, and mailer tests with:

```sh
flask test
```

Run browser tests separately:

```sh
flask test:system
```

Both commands pass arguments to pytest:

```sh
flask test -n auto
flask test test/controllers/posts_controller_test.py
```

The commands select the `test` environment and apply pending migrations to the test database before collecting tests. Each test that inherits from a Flaskteroids test class runs in a transaction. The framework rolls it back after the test.

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
playwright install chromium
```
