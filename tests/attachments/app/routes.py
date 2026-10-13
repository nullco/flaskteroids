def register(route):
    route.resources("documents", only=["create"])
