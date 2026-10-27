def register(route):
    route.get("/catalog/", to="catalog#index", aka="catalog")
    route.get("/catalog/show/", to="catalog#show")
