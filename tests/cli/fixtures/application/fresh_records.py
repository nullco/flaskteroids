from app.models.post import Post
from wsgi import app

with app.app_context():
    post = Post.create(title="first")
    assert post.id
    assert Post.find(post.id).title == "first"
    assert post.update(title="second")
    assert post.reload().title == "second"
    assert Post.where(title="second").count() == 1
