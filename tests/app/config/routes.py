def register(route):
    route.get("/up/", to="flaskteroids/health#show")
    route.resources("users")
