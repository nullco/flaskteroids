from app.models.post import Post
from sqlalchemy import select
from wsgi import app

with app.app_context():
    database = app.extensions["flaskteroids.db"]
    Post.count()
    post = Post.create(title="standalone-commit", content="durable")
    with database.new_session() as independent:
        assert independent.get(Post, post.id).content == "durable"

    try:
        with Post.transaction():
            Post.create(title="outer-rollback")
            raise RuntimeError("abort")
    except RuntimeError:
        pass
    assert Post.find_by(title="outer-rollback") is None

    with Post.transaction():
        first = Post.create(title="outer-kept")
        try:
            with Post.transaction(requires_new=True):
                Post.create(title="savepoint-rollback")
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        last = Post.create(title="outer-also-kept")
    with database.new_session() as independent:
        assert independent.get(Post, first.id) is not None
        assert independent.get(Post, last.id) is not None
        assert (
            independent.scalar(select(Post).filter_by(title="savepoint-rollback"))
            is None
        )
    for record in (post, first, last):
        assert record.destroy()
