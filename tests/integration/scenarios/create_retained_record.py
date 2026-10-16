from app.models.post import Post
from wsgi import app

with app.app_context():
    post = Post.create(title="retained", content="original")
    assert post.id
