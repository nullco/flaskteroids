from flaskteroids.controller import helper
from tests.views.fixtures.controllers.posts_controller import PostsController


class SpecialPostsController(PostsController):
    helper("chosen", "admin/money")
