def register(route):
    route.resources(
        "products",
        nested=lambda child: child.resources("subscribers", only=["create"]),
    )
    route.get("/unsubscribe/<token>/", to="unsubscribes#show", aka="unsubscribe")
    route.post(
        "/unsubscribe/<token>/", to="unsubscribes#destroy", aka="cancel_subscription"
    )
