def register(route):
    route.get("/catalog/", to="catalog#index", as_="catalog")
    route.get("/catalog/show/", to="catalog#show")
