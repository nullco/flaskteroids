def register(route):
    route.get("/posts/preview/", to="posts#preview", aka="preview_posts")
    route.get("/posts/<id>/refresh/", to="posts#refresh", aka="refresh_post")
    route.resources("posts")
