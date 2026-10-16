from app.models.post import Post
from wsgi import app

with app.app_context():
    assert "published" not in Post.new().column_names
