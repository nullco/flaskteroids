def register(route):
    route.root(to="posts#show")
    route.get("/special", to="special_posts#show")
