def register(route):
    route.get("/posts/preview/", to="posts#preview", as_="preview_posts")
    route.get("/posts/<id>/refresh/", to="posts#refresh", as_="refresh_post")
    route.resources("posts")
