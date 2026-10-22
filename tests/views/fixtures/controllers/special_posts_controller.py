from flaskteroids import rules
from flaskteroids.controller import helper
from tests.views.fixtures.controllers.posts_controller import PostsController


@rules(helper("chosen", "admin/money"))
class SpecialPostsController(PostsController):
    pass
