from app.models.post import Post
from wsgi import app

with app.app_context():
    post = Post.find_by(title="retained")
    assert post.content == "original"
    assert post.update(content="updated")
    assert post.reload().content == "updated"
