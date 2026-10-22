def register(route):
    route.root(to="products#index")
    route.resources(
        "products",
        nested=lambda child: child.resources(
            "subscribers", only=["new", "create", "edit", "update"]
        ),
    )
    route.get("/catalog", to="catalog#index")
    route.get("/catalog/edit", to="catalog#edit")
    route.resource("session", only=["new", "create", "destroy"])
    route.resources("passwords", param="token")
