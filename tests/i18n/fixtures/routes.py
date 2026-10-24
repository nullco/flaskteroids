def register(route):
    route.get("/products/", to="products#index")
    route.get("/products/show/", to="products#show")
    route.get("/products/fail/", to="products#fail")
    route.get("/products/redirect/", to="products#redirect")
