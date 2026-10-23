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

Both commands use pytest, so you can focus on one file or run tests in parallel:

```sh
bin/flask test -n auto
bin/flask test test/controllers/posts_controller_test.py
```

The commands use your `test` environment and apply pending migrations. Tests that
inherit from Flaskteroids test classes roll back their database changes, keeping
each test independent.

For upload tests, put example files in `test/fixtures/files` and use
`fixture_file_upload('avatar.png')`. Uploads use temporary storage, leaving your
real files untouched. See [Attachments](other/attachments.md#tests) for examples.

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

Each test gets its declared fixtures, and its changes are rolled back afterward.
Use fixture labels rather than hard-coded IDs; generated IDs may have gaps.

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

Use `self.fill_in_rich_text_area("Content", with_="<div>Hello</div>")` to fill a
Trix editor by its label. The value is HTML, loaded through the editor API. See
[Rich text](other/rich_text.md) for setup and model fixtures.

Flaskteroids includes the Playwright Python package, but not its browser binaries. Install Chromium before your first system test run:

```sh
.venv/bin/playwright install chromium
```
