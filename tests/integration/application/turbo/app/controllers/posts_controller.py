from http import HTTPStatus

from app.controllers.application_controller import ApplicationController
from app.models.post import Post

from flaskteroids.actions import before_action
from flaskteroids.routes import post_path, posts_path


class PostsController(ApplicationController):
    before_action("_set_post", only=["show", "edit", "update", "destroy", "refresh"])

    def index(self):
        self.posts = list(Post.order("id"))
        self.post = Post.new()

    def show(self):
        pass

    def edit(self):
        pass

    def preview(self):
        self.post = Post.first()
        # Exercise the controller API separately from the template context helpers.
        self.requested_frame = self.turbo_frame_request_id
        self.is_frame = self.turbo_frame_request

    def create(self):
        self.post = Post.new(**self._post_params())
        if self.post.save():
            self.count = Post.count()
            return self.respond_to(
                turbo_stream=lambda: self.render("create"),
                html=lambda: self.redirect_to(
                    post_path(self.post), status=HTTPStatus.SEE_OTHER
                ),
            )
        return self.render("edit", status=HTTPStatus.UNPROCESSABLE_ENTITY)

    def update(self):
        if self.post.update(**self._post_params()):
            # Ordinary Turbo forms also accept streams. Offer only HTML here so
            # the redirect is followed and its matching record frame extracted.
            return self.respond_to(
                html=lambda: self.redirect_to(
                    post_path(self.post), status=HTTPStatus.SEE_OTHER
                )
            )
        return self.render("edit", status=HTTPStatus.UNPROCESSABLE_ENTITY)

    def destroy(self):
        self.post.destroy()
        return self.respond_to(
            turbo_stream=lambda: self.render(
                turbo_stream=[
                    self.turbo_stream.remove(self.post),
                    self.turbo_stream.update("post_count", str(Post.count())),
                    self.turbo_stream.update("status", "Post removed"),
                ]
            ),
            html=lambda: self.redirect_to(posts_path(), status=HTTPStatus.SEE_OTHER),
        )

    def refresh(self):
        return self.respond_to(
            turbo_stream=lambda: self.render(
                turbo_stream=[
                    self.turbo_stream.replace(self.post),
                    self.turbo_stream.update("status", "Post refreshed"),
                ]
            ),
            html=lambda: self.redirect_to(post_path(self.post)),
        )

    def _set_post(self):
        self.post = Post.find(id=self.params["id"])

    def _post_params(self):
        return self.params.expect(post=["title"])
