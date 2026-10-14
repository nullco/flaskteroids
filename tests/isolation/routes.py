def register(routes):
    routes.get("/counter/", to="counter#index")
    routes.get("/up/", to="flaskteroids/health#show")
