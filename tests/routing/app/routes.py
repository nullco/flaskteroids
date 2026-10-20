def register(route):
    route.resource("probe")
    route.resources("products", nested=lambda child: child.resources("subscribers"))
